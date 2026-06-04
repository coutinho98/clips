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
FONT_SIZE = 10
MAX_CHARS_PER_LINE = 42
MAX_LINES = 2
TEXT_MARGIN_BOTTOM = 40


def gerar_legendas_estilizadas(segmentos, inicio_global, fim_global,
                                estilo="neon", fps=24):
    frames_dir = os.path.join(PASTA_TEMP, "legendas_frames")
    os.makedirs(frames_dir, exist_ok=True)

    duracao = fim_global - inicio_global
    n_frames = int(duracao * fps)

    w, h = RESOLUCAO

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
                segmentos_filtrados.append({
                    "inicio": seg["inicio"] - inicio_global,
                    "fim": seg["fim"] - inicio_global,
                    "texto": texto,
                })

    for f_idx in range(n_frames):
        tempo_atual = f_idx / fps

        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        safe_top_y = int(h * 0.15) + 10

        for seg in segmentos_filtrados:
            if seg["inicio"] <= tempo_atual <= seg["fim"]:
                texto = seg["texto"]
                linhas = _quebrar_texto_legenda(texto, max_chars=MAX_CHARS_PER_LINE)
                texto_formatado = "\n".join(linhas)

                _desenhar_legenda_filme(draw, texto_formatado, font, w, h, estilo)
                break

        if tempo_atual < 3.5 and segmentos_filtrados:
            _desenhar_hook_barra(draw, font_hook, w, safe_top_y)

        img.convert("RGB").save(f"{frames_dir}/frame_{f_idx:05d}.png")

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

    elif estilo == "karaoke":
        draw.multiline_text((x + 2, y + 2), texto, fill=(0, 0, 0, 180), font=font)
        draw.multiline_text((x, y), texto, fill=(255, 255, 80), font=font)

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
    linhas = []
    linha_atual = ""

    for palavra in palavras:
        if len(palavra) > max_chars:
            palavra = palavra[:max_chars - 1] + "…"

        if not linha_atual:
            linha_atual = palavra
        elif len(linha_atual) + 1 + len(palavra) <= max_chars:
            linha_atual += " " + palavra
        else:
            linhas.append(linha_atual)
            linha_atual = palavra

    if linha_atual:
        linhas.append(linha_atual)

    if len(linhas) > MAX_LINES:
        linhas = linhas[:MAX_LINES]
        ultima = linhas[-1]
        if len(ultima) + 1 <= max_chars:
            linhas[-1] = ultima.rstrip(".,;:!?") + "…"
        else:
            linhas[-1] = ultima[:max_chars - 1] + "…"

    return linhas


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

    nome_arquivo = titulo.replace(" ", "_").replace("/", "_")[:50]
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

    return caminho_saida


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
