import os
import re
import subprocess
from pathlib import Path
from config import RESOLUCAO, PASTA_TEMP, PASTA_OUTPUT, get_watermark

SAFE_ZONE_TOP_PCT = 0.15
REELS_MAX_DURACAO = 999
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


_PALAVRAS_VALIDAS_CURTAS = {
    "eu", "tu", "ele", "ela", "nós", "nóis", "vocês", "vcs",
    "sim", "não", "nao", "né", "né?", "tá", "ta", "to", "tô",
    "há", "oh", "ah", "eh", "uh", "um", "uma", "uns", "umas",
    "é", "e", "ou", "me", "te", "se", "lhe", "nos", "vos",
    "o", "a", "os", "as", "ao", "aos", "à", "às",
    "de", "do", "da", "dos", "das", "em", "no", "na", "nos", "nas",
    "por", "pra", "pro", "pelo", "pela",
    "com", "sem", "sob", "sobre",
    "que", "quem", "quê", "qual", "quais", "quando", "onde",
    "como", "assim", "aqui", "ali", "lá", "cá",
    "já", "jamais", "nunca", "sempre", "ainda", "também", "tbm",
    "mais", "menos", "muito", "pouco", "bem", "mal",
    "isto", "isso", "esse", "essa", "este", "esta",
    "ele", "ela", "eles", "elas", "só", "so",
    "pai", "mãe", "filho", "Deus",
    "ok", "okay", "wow", "hey", "ei", "ui",
    "claro", "certo", "boa", "bom", "ruim",
    "tem", "têm", "foi", "vem", "vai", "deu",
    "pode", "deve", "quer", "ser", "ver",
    "amo", "amar", "dor", "sol", "mar", "ar", "fim",
    "teu", "tua", "nó", "nós", "deu", "diz", "viu",
    "pé", "mão", "pai", "sim", "não", "sim?",
    "cu", "rê", "não", "sim", "dê", "mim", "ti",
    "né", "vê", "pô", "sei", "sê", "som", "cor",
    "sim", "nem", "têm", "for", "dar", "rir", "ler",
    "pcd", "hiv", "uv", "ppd",
}


def _limpar_texto_para_legenda(texto):
    texto = texto.strip()
    if not texto:
        return ""
    texto = re.sub(r'["\u201c\u201d][^"\u201c\u201d]{0,15}["\u201c\u201d]', '', texto)
    texto = re.sub(r'\.{2,}', '...', texto)
    texto = re.sub(r'\?{2,}', '?', texto)
    texto = re.sub(r'!{2,}', '!', texto)
    texto = re.sub(r',{2,}', ',', texto)
    texto = re.sub(r'\s*,\s*,\s*', ', ', texto)
    texto = re.sub(r'(?:^|\s),', '', texto)
    palavras = texto.split()
    palavras_limpas = []
    for p in palavras:
        p_lower = p.rstrip('.,;:!?').lower()
        if len(p_lower) <= 3 and p_lower not in _PALAVRAS_VALIDAS_CURTAS:
            continue
        palavras_limpas.append(p)
    texto = " ".join(palavras_limpas)
    texto = re.sub(r'^\s*[,.:;]\s*', '', texto)
    if len(palavras_limpas) <= 3 and texto.endswith('.'):
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
Style: Hook,FiraSans-SemiBold,80,&H00FFFFFF,&H00000000,&H00000000,&HF0000000,-1,0,0,0,100,100,2,0,1,4,2,8,20,20,0,1

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


def _add_hook_to_ass(ass_content, hook_text, duracao_corte):
    if not hook_text:
        return ass_content
    hook_dur = min(3.5, duracao_corte * 0.15)
    escaped = _escape_ass(hook_text.upper())
    dialogue = f"Dialogue: 2,0:00:00.00,{_format_ass_time(hook_dur)},Hook,,0,0,0,,{{\\fad(300,500)}}{escaped}\n"
    insert_pos = ass_content.rfind("Dialogue:")
    if insert_pos == -1:
        return ass_content + dialogue
    while insert_pos > 0 and ass_content[insert_pos - 1] != '\n':
        insert_pos -= 1
    return ass_content[:insert_pos] + dialogue + ass_content[insert_pos:]


_PALAVRAS_DESCARTAVEIS = {
    "é", "hmm", "mm", "ah", "eh", "uh", "oh", "hm", "rr", "h", "eh",
    "né", "tá", "ta", " tô", "tipo", "assim", "cara", "velho",
}


def _palavra_valida(word):
    w = word.rstrip('.,;:!?').lower().strip()
    if not w:
        return False
    if len(w) <= 1:
        return False
    if w in _PALAVRAS_DESCARTAVEIS:
        return False
    return True


def _segmentos_para_grupos(segmentos, inicio_global, fim_global,
                           max_palavras=5, max_duracao=1.8):
    grupos = []

    for seg in segmentos:
        if seg["fim"] < inicio_global or seg["inicio"] > fim_global:
            continue

        t_start = max(seg["inicio"], inicio_global)
        t_end = min(seg["fim"], fim_global)

        raw_words = []
        for wd in (seg.get("words") or []):
            if not isinstance(wd, dict):
                continue
            w_start = wd.get("inicio", wd.get("start", 0))
            w_end = wd.get("fim", wd.get("end", 0))
            w_text = wd.get("texto", wd.get("word", "")).strip()
            if w_text and w_end > t_start and w_start < t_end:
                raw_words.append((max(w_start, t_start), min(w_end, t_end), w_text))

        if not raw_words:
            texto = _limpar_texto_para_legenda(seg["texto"].strip())
            if texto:
                grupos.append({
                    "t_start": t_start, "t_end": t_end,
                    "texto": _quebrar_texto_legenda(texto)[0],
                    "words": [],
                })
            continue

        current = []
        g_start = None

        for ws, we, wt in raw_words:
            if not _palavra_valida(wt):
                continue
            if g_start is None:
                g_start = ws
            current.append((ws, we, wt))

            should_break = (
                len(current) >= max_palavras
                or (we - g_start) >= max_duracao
            )
            if should_break:
                grupos.append(_make_grupo(current))
                current = []
                g_start = None

        if current:
            grupos.append(_make_grupo(current))

    grupos.sort(key=lambda g: g["t_start"])
    return grupos


def _make_grupo(words):
    texto = " ".join(w[2] for w in words)
    texto = re.sub(r'\s{2,}', ' ', texto).strip()
    return {
        "t_start": words[0][0],
        "t_end": words[-1][1],
        "texto": texto,
        "words": words,
    }


def _gerar_ass_karaoke(segmentos, inicio_global, fim_global, video_w, video_h):
    ass = _build_ass_header(video_w, video_h)
    grupos = _segmentos_para_grupos(segmentos, inicio_global, fim_global)

    prev_end = inicio_global
    for grupo in grupos:
        t_start = max(grupo["t_start"], prev_end)
        t_end = grupo["t_end"]
        if t_start >= t_end:
            continue

        texto = _quebrar_texto_legenda(grupo["texto"])[0]
        escaped = _escape_ass(texto)
        ass += f"Dialogue: 0,{_format_ass_time(t_start - inicio_global)},{_format_ass_time(t_end - inicio_global)},Base,,0,0,0,,{escaped}\n"

        words = grupo["words"]
        if not words:
            palavras = texto.split()
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
    grupos = _segmentos_para_grupos(segmentos, inicio_global, fim_global)

    prev_end = inicio_global
    for grupo in grupos:
        t_start = max(grupo["t_start"], prev_end)
        t_end = grupo["t_end"]
        if t_start >= t_end:
            continue

        texto = _quebrar_texto_legenda(grupo["texto"])[0]
        escaped = _escape_ass(texto)
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
                              fade_transition=0.0, zoom_dinamico=False, output_dir=None,
                              hook_text=None, categoria=None):
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

    ass_content = _add_hook_to_ass(ass_content, None, fim_seg - inicio_seg)

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
            crop_w = int(orig_h * 9 / 16)
            if crop_w <= orig_w:
                smart_filter = None
                try:
                    from modules.smart_framer import gerar_smart_crop_filter
                    smart_filter = gerar_smart_crop_filter(
                        caminho_video, inicio_seg, fim_seg,
                        orig_w=orig_w, orig_h=orig_h, crop_w=crop_w,
                        target_w=video_w, target_h=video_h,
                        categoria=categoria,
                    )
                except Exception as e:
                    print(f"  [SMART-FRAME] Erro: {e}, usando fallback centro")
                if smart_filter:
                    vf_parts.append(smart_filter)
                else:
                    x_center = orig_w // 2
                    x1 = max(0, x_center - crop_w // 2)
                    vf_parts.append(f"crop={crop_w}:{orig_h}:{x1}:0")
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
    ]

    wm = get_watermark()
    if wm:
        cmd.extend(["-i", wm["path"]])
        fc = f"[0:v]{vf}[base]"
        fc += f";[1:v]scale={wm['size']}:-1,format=rgba,colorchannelmixer=aa={wm['opacity']}[wm]"
        fc += f";[base][wm]overlay={wm['pos']}[vout]"
        cmd.extend(["-filter_complex", fc, "-map", "[vout]", "-map", "0:a?"])
    else:
        cmd.extend(["-vf", vf])

    cmd.extend([
        "-af", af,
        "-c:v", "h264_nvenc",
        "-preset", "p4",
        "-cq", "23",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        caminho_saida,
    ])

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


_frame_cache = {}
_frame_cache_max = 20

PREVIEW_W = 360
PREVIEW_H = 640


def _get_cached_frame(video_path, tempo_preview, crop_vertical):
    import io
    from PIL import Image

    cache_key = (video_path, round(tempo_preview, 1))
    if cache_key in _frame_cache:
        return _frame_cache[cache_key].copy()

    w_vid, h_vid = RESOLUCAO
    frame_img = None

    if video_path and os.path.exists(video_path):
        try:
            result = subprocess.run([
                "ffmpeg", "-y", "-ss", str(tempo_preview),
                "-i", video_path, "-vframes", "1",
                "-f", "image2pipe", "-vcodec", "mjpeg", "-q:v", "5", "-",
            ], capture_output=True, timeout=10)
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
                frame_img = frame_img.resize((w_vid, h_vid), Image.BILINEAR)
        except Exception:
            pass

    if frame_img is None:
        frame_img = Image.new("RGBA", (w_vid, h_vid), (30, 30, 40, 255))

    if len(_frame_cache) >= _frame_cache_max:
        _frame_cache.pop(next(iter(_frame_cache)))
    _frame_cache[cache_key] = frame_img.copy()

    return frame_img


def _generate_preview_frame(cut_id, meta, estilo, crop_vertical):
    import io
    from PIL import Image, ImageDraw, ImageFont

    inicio = meta.get("inicio", 0)
    fim = meta.get("fim", 10)
    video_path = meta.get("video_origem", "")
    fallback = meta.get("fallback", False)
    segmentos = meta.get("segmentos", [])
    hook_text = meta.get("hook_text", "")

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

    frame_img = _get_cached_frame(video_path, tempo_preview, crop_vertical)

    scale_x = PREVIEW_W / RESOLUCAO[0]
    scale_y = PREVIEW_H / RESOLUCAO[1]
    frame_img = frame_img.resize((PREVIEW_W, PREVIEW_H), Image.BILINEAR)

    w_vid, h_vid = PREVIEW_W, PREVIEW_H
    preview_font_size = max(10, int(FONT_SIZE * scale_x))
    preview_margin = int(TEXT_MARGIN_BOTTOM * scale_y)
    preview_hook_font_size = max(12, int(64 * scale_x))

    seg_ativo = None
    for seg in segmentos:
        if seg["fim"] >= tempo_preview and seg["inicio"] <= tempo_preview:
            seg_ativo = seg
            break
    if not seg_ativo and segmentos:
        seg_ativo = segmentos[len(segmentos) // 2]

    try:
        font = ImageFont.truetype(FONT_PATH, preview_font_size)
    except Exception:
        font = ImageFont.load_default()

    if hook_text:
        try:
            hook_font = ImageFont.truetype(FONT_PATH, preview_hook_font_size)
        except Exception:
            hook_font = font
        hook_upper = hook_text.upper()
        max_w = w_vid - int(60 * scale_x)
        words = hook_upper.split()
        lines = []
        current_line = ""
        for w in words:
            test = f"{current_line} {w}".strip()
            bbox = draw_text_bbox(hook_font, test)
            if bbox[2] - bbox[0] > max_w and current_line:
                lines.append(current_line)
                current_line = w
            else:
                current_line = test
        if current_line:
            lines.append(current_line)
        lines = lines[:3]

        bar_h = int(30 * scale_y) + len(lines) * int(80 * scale_y)
        bar = Image.new("RGBA", (w_vid, bar_h), (0, 0, 0, 180))
        frame_img = Image.alpha_composite(frame_img, bar)

        overlay2 = Image.new("RGBA", (w_vid, h_vid), (0, 0, 0, 0))
        draw2 = ImageDraw.Draw(overlay2)
        y = int(15 * scale_y)
        for line in lines:
            bbox = draw_text_bbox(hook_font, line)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            x = (w_vid - tw) // 2
            draw2.text((x + 2, y + 2), line, fill=(0, 0, 0, 220), font=hook_font)
            draw2.text((x, y), line, fill=(255, 255, 255, 255), font=hook_font)
            y += th + int(10 * scale_y)
        frame_img = Image.alpha_composite(frame_img, overlay2)

    if seg_ativo:
        texto = _limpar_texto_para_legenda(seg_ativo["texto"])
        if texto:
            texto = _quebrar_texto_legenda(texto)[0]
            bbox = draw_text_bbox(font, texto)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            x = (w_vid - tw) // 2
            y = h_vid - preview_margin - th

            overlay3 = Image.new("RGBA", (w_vid, h_vid), (0, 0, 0, 0))
            draw3 = ImageDraw.Draw(overlay3)
            draw3.text((x + 2, y + 2), texto, fill=(0, 0, 0, 180), font=font)
            hl_hex = HIGHLIGHT_COLOR.lstrip("#")
            hl_rgb = tuple(int(hl_hex[i:i+2], 16) for i in (0, 2, 4))
            draw3.text((x, y), texto, fill=hl_rgb, font=font)
            frame_img = Image.alpha_composite(frame_img, overlay3)

    return frame_img.convert("RGB")


def draw_text_bbox(font, text):
    from PIL import Image, ImageDraw
    dummy = Image.new("RGBA", (1, 1))
    draw = ImageDraw.Draw(dummy)
    return draw.textbbox((0, 0), text, font=font)
