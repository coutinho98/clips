import os
import re
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy import (
    VideoFileClip,
    ImageSequenceClip,
    CompositeVideoClip,
)
from config import RESOLUCAO, PASTA_TEMP, PASTA_OUTPUT

SAFE_ZONE_TOP_PCT = 0.15
REELS_MAX_DURACAO = 90
FONT_SIZE = 52
MAX_CHARS_PER_LINE = 35
TEXT_MARGIN_BOTTOM = 180


def _sanitize_nome(titulo, max_len=50):
    nome = titulo.replace(" ", "_").replace("/", "_")
    nome = re.sub(r'[?#%&\\<>|*]', '', nome)
    return nome[:max_len]


def gerar_legendas_estilizadas(segmentos, inicio_global, fim_global,
                                estilo="neon", fps=24):
    frames_dir = os.path.join(PASTA_TEMP, "legendas_frames")
    if os.path.exists(frames_dir):
        import shutil
        shutil.rmtree(frames_dir)
    os.makedirs(frames_dir, exist_ok=True)

    duracao = fim_global - inicio_global
    n_frames = int(duracao * fps)

    w, h = RESOLUCAO

    w_vid, h_vid = RESOLUCAO

    try:
        font = ImageFont.truetype("/usr/share/fonts/opentype/fira/FiraSans-SemiBold.otf", FONT_SIZE)
        font_hook = ImageFont.truetype("/usr/share/fonts/opentype/fira/FiraSans-SemiBold.otf", 22)
    except Exception:
        font = ImageFont.load_default()
        font_hook = font

    segmentos_filtrados = []
    for seg in segmentos:
        if seg["fim"] >= inicio_global and seg["inicio"] <= fim_global:
            texto = seg["texto"].strip()
            if texto:
                texto = _limpar_texto_para_legenda(texto)
            if texto:
                words = seg.get("words", [])
                words_ajustadas = []
                for wd in words:
                    words_ajustadas.append({
                        "inicio": wd.get("inicio", wd.get("start", 0)) - inicio_global,
                        "fim": wd.get("fim", wd.get("end", 0)) - inicio_global,
                        "texto": wd.get("texto", wd.get("word", "")).strip(),
                    })
                segmentos_filtrados.append({
                    "inicio": seg["inicio"] - inicio_global,
                    "fim": seg["fim"] - inicio_global,
                    "texto": texto,
                    "words": words_ajustadas,
                })

    for f_idx in range(n_frames):
        tempo_atual = f_idx / fps

        img = Image.new("RGBA", (w_vid, h_vid), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        safe_top_y = int(h_vid * 0.15) + 10

        for seg in segmentos_filtrados:
            if seg["inicio"] <= tempo_atual <= seg["fim"]:
                texto = seg["texto"]
                linhas = _quebrar_texto_legenda(texto, max_chars=MAX_CHARS_PER_LINE)
                texto_formatado = "\n".join(linhas)

                if estilo == "karaoke":
                    _desenhar_legenda_karaoke(draw, linhas, font, w_vid, h_vid, tempo_atual, seg.get("words", []))
                else:
                    _desenhar_legenda_filme(draw, texto_formatado, font, w_vid, h_vid, estilo)
                break

        if tempo_atual < 3.5 and segmentos_filtrados:
            _desenhar_hook_barra(draw, font_hook, w_vid, safe_top_y)

        img.save(f"{frames_dir}/frame_{f_idx:05d}.png")

    return frames_dir


def _limpar_texto_para_legenda(texto):
    texto = texto.strip()
    if not texto:
        return ""

    texto = re.sub(r'\.{2,}', '...', texto)
    texto = re.sub(r'\?{2,}', '?', texto)
    texto = re.sub(r'!{2,}', '!', texto)
    texto = re.sub(r',{2,}', ',', texto)

    palavras = texto.split()
    if len(palavras) <= 3 and texto.endswith('.'):
        if not re.search(r'[.!?]$', texto.rstrip('.')):
            texto = texto.rstrip('.')

    texto = re.sub(r'\s{2,}', ' ', texto).strip()
    return texto


def _desenhar_legenda_karaoke(draw, linhas, font, largura, altura, tempo_atual, words_com_ts):
    palavras_texto = []
    for linha in linhas:
        for p in linha.split():
            palavras_texto.append(p)

    total_palavras = len(palavras_texto)
    if total_palavras == 0:
        return

    if words_com_ts and len(words_com_ts) >= total_palavras * 0.5:
        palavras_acesas = 0
        for w in words_com_ts:
            w_inicio = w.get("inicio", 0)
            w_fim = w.get("fim", 0)
            if tempo_atual >= w_inicio:
                palavras_acesas += 1
    else:
        primeira = palavras_texto[0].lower().strip(".,;:!?")
        ultima = palavras_texto[-1].lower().strip(".,;:!?")
        t_inicio = None
        t_fim = None
        for w in words_com_ts:
            w_txt = w.get("texto", "").lower().strip(".,;:!?")
            if t_inicio is None and (w_txt == primeira or primeira in w_txt):
                t_inicio = w.get("inicio", 0)
            if ultima in w_txt or w_txt == ultima:
                t_fim = w.get("fim", 0)

        if t_inicio is not None and t_fim is not None and t_fim > t_inicio:
            progresso = (tempo_atual - t_inicio) / (t_fim - t_inicio)
        else:
            return

        palavras_acesas = int(progresso * total_palavras)
        if progresso > 0:
            palavras_acesas = min(palavras_acesas + 1, total_palavras)

    texto_formatado = "\n".join(linhas)
    bbox = draw.multiline_textbbox((0, 0), texto_formatado, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x_base = (largura - tw) // 2
    y_base = altura - TEXT_MARGIN_BOTTOM - th

    draw.multiline_text((x_base + 2, y_base + 2), texto_formatado, fill=(0, 0, 0, 180), font=font)
    draw.multiline_text((x_base, y_base), texto_formatado, fill=(180, 180, 180), font=font)

    cor_highlight = (255, 255, 50)
    idx_global = 0
    y_cursor = y_base

    for linha_idx, linha in enumerate(linhas):
        palavras_linha = linha.split()
        linha_largura = draw.textlength(linha, font=font)
        x_linha = (largura - linha_largura) // 2

        x_cursor = x_linha
        for palavra in palavras_linha:
            espaco = draw.textlength(" ", font=font)
            if idx_global < palavras_acesas:
                draw.text((x_cursor + 1, y_cursor + 1), palavra, fill=(0, 0, 0, 120), font=font)
                draw.text((x_cursor, y_cursor), palavra, fill=cor_highlight, font=font)
            x_cursor += draw.textlength(palavra, font=font) + espaco
            idx_global += 1

        if linha_idx < len(linhas) - 1:
            y_cursor += draw.textbbox((0, 0), linha, font=font)[3] - draw.textbbox((0, 0), linha, font=font)[1]
            y_cursor += draw.textbbox((0, 0), "\n", font=font)[3] - draw.textbbox((0, 0), "\n", font=font)[1]


def _desenhar_legenda_filme(draw, texto, font, largura, altura, estilo):
    bbox = draw.multiline_textbbox((0, 0), texto, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (largura - tw) // 2
    y = altura - TEXT_MARGIN_BOTTOM - th

    if estilo == "neon":
        pad_x, pad_y = 12, 6
        draw.rounded_rectangle(
            [(x - pad_x, y - pad_y), (x + tw + pad_x, y + th + pad_y)],
            radius=4,
            fill=(0, 0, 0, 160),
        )
        draw.multiline_text((x + 1, y + 1), texto, fill=(0, 0, 0, 200), font=font)
        draw.multiline_text((x, y), texto, fill="white", font=font)

    elif estilo == "box":
        box_pad = 14
        draw.rounded_rectangle(
            [(x - box_pad, y - box_pad),
             (x + tw + box_pad, y + th + box_pad)],
            radius=8,
            fill=(0, 0, 0, 240),
        )
        draw.multiline_text((x, y), texto, fill="white", font=font)

    elif estilo == "sombra":
        draw.multiline_text((x + 2, y + 2), texto, fill=(0, 0, 0, 200), font=font)
        draw.multiline_text((x, y), texto, fill="white", font=font)

    else:
        draw.multiline_text((x, y), texto, fill="white", font=font)


def _desenhar_hook_barra(draw, font, largura, y_top):
    barra_h = 50
    draw.rounded_rectangle(
        [(20, y_top), (largura - 20, y_top + barra_h)],
        radius=25,
        fill=(0, 0, 0, 160),
    )


def _quebrar_texto_legenda(texto, max_chars=MAX_CHARS_PER_LINE):
    palavras = texto.split()
    linha = ""
    for palavra in palavras:
        if not linha:
            linha = palavra
        elif len(linha) + 1 + len(palavra) <= max_chars:
            linha += " " + palavra
        else:
            break
    if len(linha) > max_chars:
        linha = linha[:max_chars - 1] + "…"
    return [linha]


def gerar_video_com_legendas(caminho_video, segmentos, inicio_seg, fim_seg,
                              titulo="corte", estilo="neon", crop_vertical=True):
    if fim_seg - inicio_seg > REELS_MAX_DURACAO:
        fim_seg = inicio_seg + REELS_MAX_DURACAO

    print(f"  Gerando vídeo com legendas ({estilo}): {inicio_seg:.1f}s - {fim_seg:.1f}s")

    video = VideoFileClip(caminho_video)

    if fim_seg > video.duration:
        fim_seg = video.duration
    if inicio_seg < 0:
        inicio_seg = 0

    clip = video.subclipped(inicio_seg, fim_seg)

    if crop_vertical:
        clip = _aplicar_crop_vertical(clip)

    fps = 24
    frames_legendas = gerar_legendas_estilizadas(
        segmentos, inicio_seg, fim_seg, estilo=estilo, fps=fps
    )

    w, h = clip.size
    n_frames = int(clip.duration * fps)

    frames_saida_dir = os.path.join(PASTA_TEMP, "frames_com_legenda")
    if os.path.exists(frames_saida_dir):
        import shutil
        shutil.rmtree(frames_saida_dir)
    os.makedirs(frames_saida_dir, exist_ok=True)

    for f_idx in range(n_frames):
        t = f_idx / fps
        frame = clip.get_frame(t)
        frame_img = Image.fromarray(frame).convert("RGBA")

        legenda_path = os.path.join(frames_legendas, f"frame_{f_idx:05d}.png")
        if os.path.exists(legenda_path):
            legenda_img = Image.open(legenda_path).convert("RGBA")
            legenda_img = legenda_img.resize((w, h), Image.LANCZOS)
            frame_img = Image.alpha_composite(frame_img, legenda_img)

        frame_img.convert("RGB").save(
            os.path.join(frames_saida_dir, f"frame_{f_idx:05d}.jpg"),
            quality=90,
        )

    video_final = ImageSequenceClip(frames_saida_dir, fps=fps)
    video_final = video_final.with_audio(clip.audio)

    nome_arquivo = _sanitize_nome(titulo)
    caminho_saida = os.path.join(PASTA_OUTPUT, f"corte_{nome_arquivo}.mp4")

    print(f"  Encodando vídeo final com legendas...")
    video_final.write_videofile(
        caminho_saida,
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        audio_bitrate="192k",
        preset="fast",
        threads=4,
        logger=None,
    )

    clip.close()
    video.close()

    _mover_moov_faststart(caminho_saida)

    return caminho_saida


def _mover_moov_faststart(caminho_video):
    import subprocess
    try:
        resultado = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", caminho_video],
            capture_output=True, text=True, timeout=10,
        )
        if resultado.returncode != 0:
            return
    except Exception:
        return

    tmp_path = caminho_video + ".tmp.mp4"
    try:
        subprocess.run([
            "ffmpeg", "-y", "-i", caminho_video,
            "-c", "copy", "-movflags", "+faststart",
            tmp_path,
        ], capture_output=True, text=True, timeout=120)
        import shutil
        shutil.move(tmp_path, caminho_video)
    except Exception:
        import os
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def _aplicar_crop_vertical(clip):
    w, h = clip.size

    if h > w:
        return clip.resized(RESOLUCAO)

    target_ratio = 9 / 16
    current_ratio = w / h

    if current_ratio < target_ratio:
        new_h = int(w / target_ratio)
        y_center = h // 2
        y1 = max(0, y_center - new_h // 2)
        y2 = min(h, y1 + new_h)
        clip = clip.cropped(y1=y1, y2=y2)
    else:
        new_w = int(h * target_ratio)
        x_center = w // 2
        x1 = max(0, x_center - new_w // 2)
        x2 = min(w, x1 + new_w)
        clip = clip.cropped(x1=x1, x2=x2)

    clip = clip.resized(RESOLUCAO)
    return clip
