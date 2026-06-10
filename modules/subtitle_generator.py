import os
import re
import subprocess
from pathlib import Path
from config import RESOLUCAO, PASTA_TEMP, PASTA_OUTPUT

SAFE_ZONE_TOP_PCT = 0.15
REELS_MAX_DURACAO = 60
FONT_SIZE = 52
MAX_CHARS_PER_LINE = 35
TEXT_MARGIN_BOTTOM = 180
FONT_PATH = "/usr/share/fonts/opentype/fira/FiraSans-SemiBold.otf"
BASE_COLOR = "#B4B4B4"
HIGHLIGHT_COLOR = "#FFFF32"


def _sanitize_nome(titulo, max_len=50):
    nome = titulo.replace(" ", "_").replace("/", "_")
    nome = re.sub(r'[?#%&\\<>|*]', '', nome)
    return nome[:max_len]


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


def _escape_ass(text):
    return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}").replace("\n", "\\N")


def _format_ass_time(seconds):
    if seconds < 0:
        seconds = 0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int((seconds % 1) * 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _hex_to_ass(hex_color):
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return f"&H00{b:02X}{g:02X}{r:02X}"


def _build_ass_header(video_w, video_h):
    margin_v = TEXT_MARGIN_BOTTOM
    base_ass = _hex_to_ass(BASE_COLOR)
    hl_ass = _hex_to_ass(HIGHLIGHT_COLOR)
    return f"""[Script Info]
ScriptType: v4.00+
PlayResX: {video_w}
PlayResY: {video_h}
Timer: 100.0000
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Base,FiraSans-SemiBold,{FONT_SIZE},{base_ass},&H00000000,&H00000000,&HA0000000,-1,0,0,0,100,100,0,0,1,2,1,2,10,10,{margin_v},1
Style: Karaoke,FiraSans-SemiBold,{FONT_SIZE},{hl_ass},&HFF000000,&HFF000000,&H00000000,-1,0,0,0,100,100,0,0,1,0,0,2,10,10,{margin_v},1
Style: Neon,FiraSans-SemiBold,{FONT_SIZE},{base_ass},&H00000000,&H00000000,&HAA000000,-1,0,0,0,100,100,0,0,1,2,1,2,10,10,{margin_v},1
Style: Box,FiraSans-SemiBold,{FONT_SIZE},{base_ass},&H00000000,&H00000000,&HFF000000,-1,0,0,0,100,100,0,0,3,2,1,2,10,10,{margin_v},1
Style: Sombra,FiraSans-SemiBold,{FONT_SIZE},{base_ass},&H00000000,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,1,2,10,10,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _get_word_timestamps(seg, inicio_global, t_start, t_end):
    words = seg.get("words", [])
    if not words:
        return []

    words_rel = []
    for wd in words:
        w_start = wd.get("inicio", wd.get("start", 0)) - inicio_global
        w_end = wd.get("fim", wd.get("end", 0)) - inicio_global
        w_text = wd.get("texto", wd.get("word", "")).strip()
        if w_text and w_end > t_start and w_start < t_end:
            words_rel.append((max(w_start, t_start), min(w_end, t_end), w_text))

    return words_rel


def _gerar_ass_karaoke(segmentos, inicio_global, fim_global, video_w, video_h):
    ass = _build_ass_header(video_w, video_h)

    filtrados = []
    for seg in segmentos:
        if seg["fim"] < inicio_global or seg["inicio"] > fim_global:
            continue
        texto = seg["texto"].strip()
        if not texto:
            continue
        texto = _limpar_texto_para_legenda(texto)
        if not texto:
            continue
        texto = _quebrar_texto_legenda(texto)[0]
        t_start = max(seg["inicio"], inicio_global)
        t_end = min(seg["fim"], fim_global)
        filtrados.append({"t_start": t_start, "t_end": t_end, "texto": texto, "words": seg.get("words", []), "seg_orig": seg})

    filtrados.sort(key=lambda s: s["t_start"])

    prev_end = inicio_global
    for item in filtrados:
        t_start = max(item["t_start"], prev_end)
        t_end = item["t_end"]
        if t_start >= t_end:
            continue

        escaped = _escape_ass(item["texto"])
        ass += f"Dialogue: 0,{_format_ass_time(t_start - inicio_global)},{_format_ass_time(t_end - inicio_global)},Base,,0,0,0,,{escaped}\n"

        words = _get_word_timestamps(item["seg_orig"], inicio_global, t_start, t_end)
        if not words:
            palavras = item["texto"].split()
            dur_total = t_end - t_start
            dur_each = dur_total / max(len(palavras), 1)
            words = []
            for idx, p in enumerate(palavras):
                ws = t_start + idx * dur_each
                we = ws + dur_each
                words.append((ws, we, p))

        k_start = words[0][0]
        k_end = words[-1][1]

        parts = []
        karaoke_elapsed = 0
        for i, (ws, we, wt) in enumerate(words):
            word_start_cs = int((ws - k_start) * 100)
            gap_cs = word_start_cs - karaoke_elapsed
            if gap_cs > 0:
                parts.append(f"{{\\k{gap_cs}}}")
            dur_cs = max(int((we - ws) * 100), 1)
            esc = _escape_ass(wt)
            sep = " " if i < len(words) - 1 else ""
            parts.append(f"{{\\k{dur_cs}}}{esc}{sep}")
            karaoke_elapsed = word_start_cs + dur_cs

        karaoke = "".join(parts)
        ass += f"Dialogue: 1,{_format_ass_time(k_start - inicio_global)},{_format_ass_time(k_end - inicio_global)},Karaoke,,0,0,0,,{karaoke}\n"

        prev_end = t_end

    return ass


def _gerar_ass_simples(segmentos, inicio_global, fim_global, video_w, video_h, estilo):
    ass = _build_ass_header(video_w, video_h)
    style_map = {"neon": "Neon", "box": "Box", "sombra": "Sombra"}
    style_name = style_map.get(estilo, "Sombra")

    filtrados = []
    for seg in segmentos:
        if seg["fim"] < inicio_global or seg["inicio"] > fim_global:
            continue
        texto = seg["texto"].strip()
        if not texto:
            continue
        texto = _limpar_texto_para_legenda(texto)
        if not texto:
            continue
        texto = _quebrar_texto_legenda(texto)[0]
        t_start = max(seg["inicio"], inicio_global)
        t_end = min(seg["fim"], fim_global)
        filtrados.append({"t_start": t_start, "t_end": t_end, "texto": texto})

    filtrados.sort(key=lambda s: s["t_start"])

    prev_end = inicio_global
    for item in filtrados:
        t_start = max(item["t_start"], prev_end)
        t_end = item["t_end"]
        if t_start >= t_end:
            continue

        escaped = _escape_ass(item["texto"])
        ass += f"Dialogue: 0,{_format_ass_time(t_start - inicio_global)},{_format_ass_time(t_end - inicio_global)},{style_name},,0,0,0,,{escaped}\n"

        prev_end = t_end

    return ass


def _probe_video(caminho_video):
    try:
        proc = subprocess.run(
            ["ffprobe", "-v", "error",
             "-show_entries", "stream=width,height,codec_type,duration",
             "-show_entries", "format=duration",
             "-of", "json", caminho_video],
            capture_output=True, text=True, timeout=10,
        )
        import json
        info = {"width": 1920, "height": 1080, "duration": 999999}
        data = json.loads(proc.stdout)
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video":
                info["width"] = int(stream.get("width", 1920))
                info["height"] = int(stream.get("height", 1080))
                if "duration" in stream:
                    info["duration"] = float(stream["duration"])
        if "format" in data and "duration" in data["format"]:
            info["duration"] = float(data["format"]["duration"])
        return info
    except Exception:
        return {"width": 1920, "height": 1080, "duration": 999999}


def gerar_video_com_legendas(caminho_video, segmentos, inicio_seg, fim_seg,
                              titulo="corte", estilo="neon", crop_vertical=True,
                              fade_transition=0.0, zoom_dinamico=False, output_dir=None):
    if fim_seg - inicio_seg > REELS_MAX_DURACAO:
        fim_seg = inicio_seg + REELS_MAX_DURACAO

    print(f"  Gerando legendas ASS ({estilo}): {inicio_seg:.1f}s - {fim_seg:.1f}s")

    nome_arquivo = _sanitize_nome(titulo)
    import hashlib
    safe_name = hashlib.md5(titulo.encode()).hexdigest()[:10]
    ass_path = os.path.join(PASTA_TEMP, f"sub_{safe_name}.ass")
    out_dir = output_dir or PASTA_OUTPUT
    caminho_saida = os.path.join(out_dir, f"corte_{nome_arquivo}.mp4")

    video_w, video_h = RESOLUCAO

    if estilo == "karaoke":
        ass_content = _gerar_ass_karaoke(segmentos, inicio_seg, fim_seg, video_w, video_h)
    else:
        ass_content = _gerar_ass_simples(segmentos, inicio_seg, fim_seg, video_w, video_h, estilo)

    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(ass_content)

    vf_parts = []

    if crop_vertical:
        probe = _probe_video(caminho_video)
        orig_w = int(probe.get("width", 1920))
        orig_h = int(probe.get("height", 1080))

        if orig_h > orig_w:
            vf_parts.append(f"scale={video_w}:{video_h}")
        else:
            target_ratio = 9 / 16
            current_ratio = orig_w / orig_h
            if current_ratio < target_ratio:
                new_h = int(orig_w / target_ratio)
                y_center = orig_h // 2
                y1 = max(0, y_center - new_h // 2)
                vf_parts.append(f"crop={orig_w}:{new_h}:0:{y1}")
            else:
                new_w = int(orig_h * target_ratio)
                x_center = orig_w // 2
                x1 = max(0, x_center - new_w // 2)
                vf_parts.append(f"crop={new_w}:{orig_h}:{x1}:0")
            vf_parts.append(f"scale={video_w}:{video_h}")

    escaped_ass = ass_path.replace("'", "'\\''").replace(":", "\\:")
    vf_parts.append(f"ass='{escaped_ass}'")

    duracao_corte = fim_seg - inicio_seg
    if fade_transition > 0:
        vf_parts.append(f"fade=t=in:st=0:d={fade_transition}")
        vf_parts.append(f"fade=t=out:st={duracao_corte - fade_transition}:d={fade_transition}")

    vf = ",".join(vf_parts)

    af = "loudnorm=I=-14:TP=-1.5:LRA=11"
    if fade_transition > 0:
        af += f",afade=t=in:st=0:d={fade_transition}"
        af += f",afade=t=out:st={duracao_corte - fade_transition}:d={fade_transition}"

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(inicio_seg),
        "-to", str(fim_seg),
        "-i", caminho_video,
        "-vf", vf,
        "-af", af,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        "-threads", "4",
        caminho_saida,
    ]

    print(f"  Encodando vídeo com legendas...")
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if proc.returncode != 0:
        print(f"  [ERRO] ffmpeg: {proc.stderr[-500:]}")
        return None

    if not os.path.exists(caminho_saida):
        return None

    tamanho_mb = os.path.getsize(caminho_saida) / (1024 * 1024)
    print(f"  Vídeo salvo: {caminho_saida} ({tamanho_mb:.1f} MB)")
    return caminho_saida


def _generate_preview_frame(cut_id, meta, estilo, crop_vertical):
    import io
    from PIL import Image, ImageDraw, ImageFont

    inicio = meta.get("inicio", 0)
    fim = meta.get("fim", 10)
    video_path = meta.get("video_origem", "")
    fallback = meta.get("fallback", False)
    segmentos = meta.get("segmentos", [])

    if fallback and video_path:
        try:
            probe = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", video_path],
                capture_output=True, text=True, timeout=10,
            )
            duracao = float(probe.stdout.strip())
        except Exception:
            duracao = 30
        tempo_preview = duracao * 0.3
    else:
        tempo_preview = inicio + min(3.0, (fim - inicio) / 2)

    w_vid, h_vid = RESOLUCAO

    if video_path and os.path.exists(video_path):
        try:
            result = subprocess.run([
                "ffmpeg", "-y", "-ss", str(tempo_preview),
                "-i", video_path, "-vframes", "1",
                "-f", "image2pipe", "-vcodec", "png", "-",
            ], capture_output=True, timeout=15)
            if len(result.stdout) > 100:
                frame_img = Image.open(io.BytesIO(result.stdout)).convert("RGBA")
                fw, fh = frame_img.size
                target_ratio = 9 / 16
                current_ratio = fw / fh
                if current_ratio > target_ratio:
                    new_w = int(fh * target_ratio)
                    x1 = (fw - new_w) // 2
                    frame_img = frame_img.crop((x1, 0, x1 + new_w, fh))
                elif current_ratio < target_ratio:
                    new_h = int(fw / target_ratio)
                    y1 = (fh - new_h) // 2
                    frame_img = frame_img.crop((0, y1, fw, y1 + new_h))
                frame_img = frame_img.resize((w_vid, h_vid), Image.LANCZOS)
            else:
                frame_img = Image.new("RGBA", (w_vid, h_vid), (30, 30, 40, 255))
        except Exception:
            frame_img = Image.new("RGBA", (w_vid, h_vid), (30, 30, 40, 255))
    else:
        frame_img = Image.new("RGBA", (w_vid, h_vid), (30, 30, 40, 255))

    seg_ativo = None
    for seg in segmentos:
        if seg["fim"] >= tempo_preview and seg["inicio"] <= tempo_preview:
            seg_ativo = seg
            break
    if not seg_ativo and segmentos:
        seg_ativo = segmentos[len(segmentos) // 2]

    try:
        font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
    except Exception:
        font = ImageFont.load_default()

    if seg_ativo:
        texto = _limpar_texto_para_legenda(seg_ativo["texto"])
        if texto:
            texto = _quebrar_texto_legenda(texto)[0]
            bbox = draw_text_bbox(font, texto)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            x = (w_vid - tw) // 2
            y = h_vid - TEXT_MARGIN_BOTTOM - th

            overlay = Image.new("RGBA", (w_vid, h_vid), (0, 0, 0, 0))
            draw = ImageDraw.Draw(overlay)
            draw.text((x + 2, y + 2), texto, fill=(0, 0, 0, 180), font=font)
            hl_hex = HIGHLIGHT_COLOR.lstrip("#")
            hl_rgb = tuple(int(hl_hex[i:i+2], 16) for i in (0, 2, 4))
            draw.text((x, y), texto, fill=hl_rgb, font=font)
            frame_img = Image.alpha_composite(frame_img, overlay)

    return frame_img.convert("RGB")


def draw_text_bbox(font, text):
    from PIL import Image, ImageDraw
    dummy = Image.new("RGBA", (1, 1))
    draw = ImageDraw.Draw(dummy)
    return draw.textbbox((0, 0), text, font=font)
