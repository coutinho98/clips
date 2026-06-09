import os
import re
import subprocess
import tempfile
from config import RESOLUCAO, PASTA_OUTPUT, PASTA_TEMP

REELS_MAX_DURACAO = 999


def detectar_faces_crop(caminho_video, inicio_seg, fim_seg, target_w, target_h):
    try:
        import cv2
    except ImportError:
        return None

    print(f"  Detectando faces para crop inteligente...")

    cap = cv2.VideoCapture(caminho_video)
    if not cap.isOpened():
        return None

    fps_video = cap.get(cv2.CAP_PROP_FPS) or 30
    frame_inicio = int(inicio_seg * fps_video)
    frame_fim = int(fim_seg * fps_video)
    total_frames = frame_fim - frame_inicio

    if total_frames <= 0:
        cap.release()
        return None

    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    face_cascade = cv2.CascadeClassifier(cascade_path)

    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_inicio)

    y_positions = []
    x_positions = []
    sample_rate = max(1, total_frames // 20)
    frames_lidos = 0

    while frames_lidos < total_frames:
        ret, frame = cap.read()
        if not ret:
            break

        if frames_lidos % sample_rate == 0:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))

            if len(faces) > 0:
                maior = max(faces, key=lambda f: f[2] * f[3])
                fx, fy, fw, fh = maior
                centro_x = fx + fw // 2
                centro_y = fy + fh // 2
                x_positions.append(centro_x)
                y_positions.append(centro_y)

        frames_lidos += 1

    cap.release()

    if not x_positions:
        return None

    orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) if cap.isOpened() else 0
    probe = _probe_video(caminho_video)
    orig_w = int(probe.get("width", 1920))
    orig_h = int(probe.get("height", 1080))

    media_x = sum(x_positions) // len(x_positions)
    media_y = sum(y_positions) // len(y_positions)

    crop_w = min(int(orig_h * 9 / 16), orig_w)
    crop_x = media_x - crop_w // 2
    crop_x = max(0, min(crop_x, orig_w - crop_w))

    print(f"  Face detectada: crop centralizado em x={crop_x} (baseado em {len(x_positions)} frames)")
    return crop_x


def extrair_corte(caminho_video, inicio_seg, fim_seg, titulo="corte",
                  crop_vertical=True, adicionar_legenda=False,
                  segmentos_legenda=None, hook_text=None,
                  bg_music_path=None, bg_music_volume=0.15,
                  estilo_legenda="neon", zoom_dinamico=False,
                  fade_transition=0.0, probe_cache=None):
    duracao = fim_seg - inicio_seg
    if duracao > REELS_MAX_DURACAO:
        fim_seg = inicio_seg + REELS_MAX_DURACAO
        print(f"  [REELS] Limitado a {REELS_MAX_DURACAO}s")

    print(f"  Extraindo corte: {inicio_seg:.1f}s - {fim_seg:.1f}s ({fim_seg - inicio_seg:.1f}s)")

    if adicionar_legenda and segmentos_legenda:
        from modules.subtitle_generator import gerar_video_com_legendas
        return gerar_video_com_legendas(
            caminho_video, segmentos_legenda, inicio_seg, fim_seg,
            titulo=titulo, estilo=estilo_legenda, crop_vertical=crop_vertical,
            fade_transition=fade_transition,
        )
    nome_arquivo = re.sub(r'[?#%&\\<>|*]', '', titulo.replace(" ", "_").replace("/", "_"))[:50]
    caminho_saida = os.path.join(PASTA_OUTPUT, f"corte_{nome_arquivo}.mp4")

    if probe_cache and caminho_video in probe_cache:
        probe = probe_cache[caminho_video]
    else:
        probe = _probe_video(caminho_video)
        if probe_cache is not None:
            probe_cache[caminho_video] = probe
    video_duration = float(probe.get("duration", 999999))
    if fim_seg > video_duration:
        fim_seg = video_duration
    if inicio_seg < 0:
        inicio_seg = 0

    vf_parts = []
    af_parts = []

    w_orig = int(probe.get("width", 1920))
    h_orig = int(probe.get("height", 1080))

    if crop_vertical and h_orig <= w_orig:
        crop_w = int(h_orig * 9 / 16)
        if crop_w <= w_orig:
            face_crop_x = detectar_faces_crop(caminho_video, inicio_seg, fim_seg, crop_w, h_orig)
            if face_crop_x is not None:
                crop_x = face_crop_x
            else:
                crop_x = (w_orig - crop_w) // 2
            vf_parts.append(f"crop={crop_w}:{h_orig}:{crop_x}:0")
        vf_parts.append(f"scale={RESOLUCAO[0]}:{RESOLUCAO[1]}")
    elif h_orig > w_orig:
        vf_parts.append(f"scale={RESOLUCAO[0]}:{RESOLUCAO[1]}")

    legendas_filter = ""
    if adicionar_legenda and segmentos_legenda:
        srt_path = _gerar_srt_corte(segmentos_legenda, inicio_seg, fim_seg)
        if srt_path:
            legendas_filter = (
                f",subtitles={srt_path}"
                f":force_style='FontName=Fira Sans SemiBold,FontSize=10,"
                f"PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,"
                f"Outline=1,Shadow=1,Alignment=2,MarginV=25'"
            )

    hook_filter = ""
    if hook_text:
        hook_path = _gerar_hook_srt(hook_text, fim_seg - inicio_seg)
        if hook_path:
            hook_filter = (
                f",subtitles={hook_path}"
                f":force_style='FontName=Fira Sans SemiBold,FontSize=9,"
                f"PrimaryColour=&H00D7FF&,OutlineColour=&H000000&,"
                f"Outline=1,Alignment=6,MarginV={int(RESOLUCAO[1] * 0.80)}'"
            )

    if vf_parts:
        video_filter = ",".join(vf_parts) + legendas_filter + hook_filter
    else:
        video_filter = legendas_filter.lstrip(",") + hook_filter

    duracao_corte = fim_seg - inicio_seg

    if fade_transition > 0:
        video_filter += f",fade=t=in:st=0:d={fade_transition}"
        video_filter += f",fade=t=out:st={duracao_corte - fade_transition}:d={fade_transition}"

    af_parts.append("loudnorm=I=-14:TP=-1.5:LRA=11")

    if fade_transition > 0:
        af_parts.append(f"afade=t=in:st=0:d={fade_transition}")
        af_parts.append(f"afade=t=out:st={duracao_corte - fade_transition}:d={fade_transition}")

    has_bg_music = bg_music_path and os.path.exists(bg_music_path)

    if has_bg_music:
        cmd = _build_cmd_bg_music(
            caminho_video, inicio_seg, fim_seg, bg_music_path,
            bg_music_volume, video_filter, af_parts, caminho_saida
        )
    else:
        cmd = _build_cmd_simple(
            caminho_video, inicio_seg, fim_seg, video_filter, af_parts, caminho_saida
        )

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if proc.returncode != 0:
            print(f"  [AVISO] Filtro falhou, tentando simples...")
            cmd_simple = [
                "ffmpeg", "-y",
                "-ss", str(inicio_seg),
                "-to", str(fim_seg),
                "-i", caminho_video,
                "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "23",
                "-c:a", "aac",
                "-b:a", "192k",
                "-movflags", "+faststart",
                "-threads", "4",
                caminho_saida,
            ]
            subprocess.run(cmd_simple, capture_output=True, text=True, timeout=300)
    except subprocess.TimeoutExpired:
        print(f"  [ERRO] Timeout ao processar corte")
        return None

    if not os.path.exists(caminho_saida):
        return None

    tamanho_mb = os.path.getsize(caminho_saida) / (1024 * 1024)
    print(f"  Corte salvo: {caminho_saida} ({tamanho_mb:.1f} MB)")
    return caminho_saida


def _build_cmd_bg_music(caminho_video, inicio_seg, fim_seg, bg_music_path,
                         bg_volume, video_filter, af_parts, caminho_saida):
    audio_filter = (
        f"[0:a]loudnorm=I=-14:TP=-1.5:LRA=11[audio];"
        f"[1:a]volume={bg_volume},afade=t=out:st={fim_seg - inicio_seg - 2}:d=2,"
        f"afade=t=in:st=0:d=1[bg];"
        f"[audio][bg]amix=inputs=2:duration=first:dropout_transition=2[aout]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(inicio_seg),
        "-to", str(fim_seg),
        "-i", caminho_video,
        "-i", bg_music_path,
        "-filter_complex", audio_filter,
        "-map", "0:v",
        "-map", "[aout]",
    ]

    if video_filter:
        cmd.extend(["-vf", video_filter])

    cmd.extend([
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        "-threads", "4",
        caminho_saida,
    ])
    return cmd


def _build_cmd_simple(caminho_video, inicio_seg, fim_seg, video_filter, af_parts, caminho_saida):
    audio_filter = ",".join(af_parts)

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(inicio_seg),
        "-to", str(fim_seg),
        "-i", caminho_video,
    ]

    if video_filter:
        cmd.extend(["-vf", video_filter])
    if audio_filter:
        cmd.extend(["-af", audio_filter])

    cmd.extend([
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        "-threads", "4",
        caminho_saida,
    ])
    return cmd


def extrair_multiplos_cortes(caminho_video, cortes, crop_vertical=True,
                              adicionar_legenda=False, transcricao=None,
                              bg_music_path=None, bg_music_volume=0.15,
                              estilo_legenda="neon", zoom_dinamico=False,
                              fade_transition=0.0):
    resultados = []
    _probe_cache = {}

    def _get_probe(path):
        if path not in _probe_cache:
            _probe_cache[path] = _probe_video(path)
        return _probe_cache[path]

    for i, corte in enumerate(cortes):
        inicio = corte.get("inicio_seg", 0)
        fim = corte.get("fim_seg", 60)
        titulo = corte.get("titulo", f"corte_{i + 1}")
        hook = corte.get("hook_text", None)

        segmentos_legenda = None
        if transcricao and adicionar_legenda:
            segmentos_legenda = _filtrar_segmentos(
                transcricao.get("segmentos", []), inicio, fim
            )

        try:
            caminho = extrair_corte(
                caminho_video, inicio, fim,
                titulo=titulo,
                crop_vertical=crop_vertical,
                adicionar_legenda=adicionar_legenda,
                segmentos_legenda=segmentos_legenda,
                hook_text=hook,
                bg_music_path=bg_music_path,
                bg_music_volume=bg_music_volume,
                estilo_legenda=estilo_legenda,
                zoom_dinamico=zoom_dinamico,
                fade_transition=fade_transition,
                probe_cache=_probe_cache,
            )
            if caminho:
                import json
                nome_arquivo = re.sub(r'[?#%&\\<>|*]', '', titulo.replace(" ", "_").replace("/", "_"))[:50]
                meta_path = os.path.join(PASTA_TEMP, f"{nome_arquivo}_meta.json")
                with open(meta_path, "w", encoding="utf-8") as mf:
                    json.dump({
                        "video_origem": caminho_video,
                        "inicio": inicio,
                        "fim": fim,
                        "titulo": titulo,
                        "segmentos": segmentos_legenda or [],
                    }, mf, ensure_ascii=False, indent=2)
                resultados.append({
                    "titulo": titulo,
                    "caminho": caminho,
                    "inicio": inicio,
                    "fim": fim,
                    "duracao": fim - inicio,
                    "score": corte.get("score_viral", 0),
                    "status": "ok",
                    "tags": corte.get("tags", []),
                    "descricao": corte.get("descricao", ""),
                })
            else:
                resultados.append({
                    "titulo": titulo,
                    "inicio": inicio,
                    "fim": fim,
                    "status": "erro",
                    "erro": "ffmpeg falhou",
                })
        except Exception as e:
            print(f"  [ERRO] Falha ao extrair corte '{titulo}': {e}")
            resultados.append({
                "titulo": titulo,
                "inicio": inicio,
                "fim": fim,
                "status": "erro",
                "erro": str(e),
            })

    return resultados


def gerar_preview(caminho_video, cortes, crop_vertical=True):
    previews = []

    for i, corte in enumerate(cortes):
        inicio = corte.get("inicio_seg", 0)
        fim = corte.get("fim_seg", 60)
        titulo = corte.get("titulo", f"preview_{i + 1}")

        thumb_time = inicio + (fim - inicio) / 2
        nome_arquivo = re.sub(r'[?#%&\\<>|*]', '', titulo.replace(" ", "_").replace("/", "_"))[:50]
        thumb_path = os.path.join(PASTA_OUTPUT, f"preview_{nome_arquivo}.jpg")

        probe = _probe_video(caminho_video)
        w_orig = int(probe.get("width", 1920))
        h_orig = int(probe.get("height", 1080))

        vf_parts = []
        if crop_vertical and h_orig <= w_orig:
            crop_w = int(h_orig * 9 / 16)
            crop_x = (w_orig - crop_w) // 2
            vf_parts.append(f"crop={crop_w}:{h_orig}:{crop_x}:0")
        vf_parts.append(f"scale={RESOLUCAO[0]}:{RESOLUCAO[1]}")

        cmd = [
            "ffmpeg", "-y",
            "-ss", str(thumb_time),
            "-i", caminho_video,
            "-vframes", "1",
            "-vf", ",".join(vf_parts),
            thumb_path,
        ]

        try:
            subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if os.path.exists(thumb_path):
                previews.append({
                    "titulo": titulo,
                    "thumb": thumb_path,
                    "inicio": inicio,
                    "fim": fim,
                    "duracao": fim - inicio,
                    "score": corte.get("score_viral", 0),
                    "hook": corte.get("hook_text", ""),
                })
                print(f"  Preview {i + 1}: {thumb_path}")
        except Exception:
            pass

    return previews


def _probe_video(caminho):
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error",
             "-show_entries", "format=duration:stream=width,height",
             "-of", "csv=p=0", caminho],
            capture_output=True, text=True,
        )
        lines = result.stdout.strip().split("\n")
        info = {}
        for line in lines:
            parts = line.split(",")
            if len(parts) >= 3:
                try:
                    info["width"] = int(parts[0]) if parts[0] else None
                    info["height"] = int(parts[1]) if parts[1] else None
                except ValueError:
                    pass
            if len(parts) == 1:
                try:
                    info["duration"] = float(parts[0])
                except ValueError:
                    pass
        return info
    except Exception:
        return {}


def _gerar_srt_corte(segmentos, inicio_global, fim_global):
    srt_path = os.path.join(PASTA_TEMP, "corte_legendas.srt")

    def fmt(seg):
        h = int(seg // 3600)
        m = int((seg % 3600) // 60)
        s = int(seg % 60)
        ms = int((seg % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    palavras = []
    for seg in segmentos:
        if seg["fim"] < inicio_global or seg["inicio"] > fim_global:
            continue

        if seg.get("words"):
            for w in seg["words"]:
                w_inicio = w.get("inicio", w.get("start", 0))
                w_fim = w.get("fim", w.get("end", 0))
                w_texto = w.get("texto", w.get("word", "")).strip()
                if w_texto:
                    palavras.append({"inicio": w_inicio, "fim": w_fim, "texto": w_texto})

    if not palavras:
        return _gerar_srt_corte_segmentos(segmentos, inicio_global, fim_global)

    duracao_corte = fim_global - inicio_global
    chunk_max = max(4, min(6, int(duracao_corte / 10)))
    chunk_dur_max = 2.0

    entradas = []
    idx = 1
    chunk_words = []
    chunk_inicio = None
    chunk_idx_start = 0

    for p_idx, p in enumerate(palavras):
        rel_inicio = p["inicio"] - inicio_global
        rel_fim = p["fim"] - inicio_global

        if rel_fim < 0 or rel_inicio > duracao_corte:
            continue

        if chunk_inicio is None:
            chunk_inicio = rel_inicio
            chunk_idx_start = p_idx

        chunk_words.append(p["texto"])
        chunk_dur = rel_fim - chunk_inicio

        is_last_word = (p_idx == len(palavras) - 1)
        should_break = len(chunk_words) >= chunk_max or chunk_dur >= chunk_dur_max

        if should_break or is_last_word:
            texto_limpo = _limpar_texto_chunk(chunk_words, p_idx == len(palavras) - 1)

            if texto_limpo:
                entradas.append(f"{idx}")
                entradas.append(f"{fmt(chunk_inicio)} --> {fmt(rel_fim)}")
                entradas.append(texto_limpo)
                entradas.append("")
                idx += 1

            chunk_words = []
            chunk_inicio = None

    if idx == 1:
        return None

    with open(srt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(entradas))

    return srt_path


def _gerar_srt_corte_segmentos(segmentos, inicio_global, fim_global):
    srt_path = os.path.join(PASTA_TEMP, "corte_legendas.srt")

    def fmt(seg):
        h = int(seg // 3600)
        m = int((seg % 3600) // 60)
        s = int(seg % 60)
        ms = int((seg % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    entradas = []
    idx = 1
    for seg in segmentos:
        rel_inicio = seg["inicio"] - inicio_global
        rel_fim = seg["fim"] - inicio_global

        if rel_fim < 0 or rel_inicio > (fim_global - inicio_global):
            continue

        rel_inicio = max(0, rel_inicio)
        rel_fim = min(fim_global - inicio_global, rel_fim)

        texto = seg["texto"].strip()
        if not texto:
            continue

        texto = _limpar_pontuacao_legenda(texto)

        if not texto:
            continue

        entradas.append(f"{idx}")
        entradas.append(f"{fmt(rel_inicio)} --> {fmt(rel_fim)}")
        entradas.append(texto)
        entradas.append("")
        idx += 1

    if idx == 1:
        return None

    with open(srt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(entradas))

    return srt_path


def _limpar_texto_chunk(palavras, is_last_chunk=False):
    palavras_limpas = []
    for i, p in enumerate(palavras):
        is_last = (i == len(palavras) - 1)
        if is_last:
            if p.endswith(('?', '!')):
                palavras_limpas.append(p)
            elif p.endswith('.'):
                palavras_limpas.append(p.rstrip('.') + '...')
            elif p.endswith('...'):
                palavras_limpas.append(p)
            elif p.endswith(','):
                palavras_limpas.append(p.rstrip(','))
            else:
                palavras_limpas.append(p.rstrip('.,;:'))
        else:
            palavras_limpas.append(p.rstrip('.,;:'))

    texto = " ".join(palavras_limpas)
    texto = re.sub(r'\s{2,}', ' ', texto).strip()
    texto = re.sub(r'\.{4,}', '...', texto)

    if len(texto) <= 1:
        return ""

    return texto


def _limpar_pontuacao_legenda(texto):
    texto = texto.strip()
    if not texto:
        return ""

    palavras = texto.split()
    if len(palavras) <= 2:
        texto = texto.rstrip('.')
        if texto.endswith(',') or texto.endswith(';'):
            texto = texto[:-1]

    texto = re.sub(r'\.{2,}', '...', texto)

    return texto.strip()


def _gerar_hook_srt(hook_text, duracao_total):
    srt_path = os.path.join(PASTA_TEMP, "corte_hook.srt")

    hook_duracao = min(3.5, duracao_total * 0.3)

    with open(srt_path, "w", encoding="utf-8") as f:
        f.write("1\n")
        f.write(f"00:00:00,000 --> 00:00:{int(hook_duracao):02d},{int((hook_duracao % 1) * 1000):03d}\n")
        f.write(f"{hook_text}\n")

    return srt_path


def _filtrar_segmentos(segmentos, inicio, fim):
    filtrados = []
    for seg in segmentos:
        if seg["fim"] >= inicio and seg["inicio"] <= fim:
            filtrados.append(seg)
    return filtrados
