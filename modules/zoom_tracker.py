import subprocess
import os
from pathlib import Path

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

try:
    import numpy as np
    HAS_NP = True
except ImportError:
    HAS_NP = False


def detectar_faces_timeline(caminho_video, inicio_seg, fim_seg, sample_interval=2.0):
    if not HAS_CV2 or not HAS_NP:
        return []

    cap = cv2.VideoCapture(caminho_video)
    if not cap.isOpened():
        return []

    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    face_cascade = cv2.CascadeClassifier(cascade_path)

    frame_inicio = int(inicio_seg * fps)
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_inicio)

    total_frames = int((fim_seg - inicio_seg) * fps)
    sample_rate = max(1, int(sample_interval * fps))

    detections = []
    frames_lidos = 0

    while frames_lidos < total_frames:
        ret, frame = cap.read()
        if not ret:
            break

        if frames_lidos % sample_rate == 0:
            tempo = inicio_seg + frames_lidos / fps
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)
            )

            if len(faces) > 0:
                maior = max(faces, key=lambda f: f[2] * f[3])
                fx, fy, fw, fh = maior
                cx = (fx + fw / 2) / orig_w
                cy = (fy + fh / 2) / orig_h
                detections.append({
                    "tempo": tempo,
                    "cx": cx,
                    "cy": cy,
                    "face_w": fw / orig_w,
                    "face_h": fh / orig_h,
                })

        frames_lidos += 1

    cap.release()
    return detections


def gerar_zoompan_keyframes(detections, orig_w, orig_h, target_w, target_h,
                            zoom_factor=1.3, smooth_window=5):
    if not detections or not HAS_NP:
        return []

    tempos = np.array([d["tempo"] for d in detections])
    cxs = np.array([d["cx"] for d in detections])
    cys = np.array([d["cy"] for d in detections])

    if len(cxs) >= smooth_window:
        kernel = np.ones(smooth_window) / smooth_window
        cxs = np.convolve(cxs, kernel, mode="same")
        cys = np.convolve(cys, kernel, mode="same")

    crop_w = int(orig_w / zoom_factor)
    crop_h = int(orig_h / zoom_factor)

    if crop_w > orig_w:
        crop_w = orig_w
    if crop_h > orig_h:
        crop_h = orig_h

    keyframes = []
    for i in range(len(detections)):
        cx = float(np.clip(cxs[i], 0, 1))
        cy = float(np.clip(cys[i], 0, 1))

        x = int(cx * orig_w - crop_w / 2)
        y = int(cy * orig_h - crop_h / 2)
        x = max(0, min(x, orig_w - crop_w))
        y = max(0, min(y, orig_h - crop_h))

        keyframes.append({
            "tempo": float(tempos[i]),
            "x": x,
            "y": y,
            "crop_w": crop_w,
            "crop_h": crop_h,
        })

    return keyframes


def aplicar_zoom_dinamico_ffmpeg(caminho_video, caminho_saida, inicio_seg, fim_seg,
                                  target_w=1080, target_h=1920, zoom_factor=1.3,
                                  fade_duration=0.3):
    if not HAS_CV2:
        return False

    detections = detectar_faces_timeline(caminho_video, inicio_seg, fim_seg)

    if not detections:
        return False

    probe = _probe_video(caminho_video)
    orig_w = int(probe.get("width", 1920))
    orig_h = int(probe.get("height", 1080))
    fps = 24

    keyframes = gerar_zoompan_keyframes(
        detections, orig_w, orig_h, target_w, target_h, zoom_factor
    )

    if not keyframes:
        return False

    duracao = fim_seg - inicio_seg
    zoompan_expr = _build_zoompan(keyframes, orig_w, orig_h, target_w, target_h, fps, duracao)

    vf_parts = [zoompan_expr]
    vf_parts.append(f"scale={target_w}:{target_h}")

    if fade_duration > 0:
        vf_parts.append(f"fade=t=in:st=0:d={fade_duration}")
        vf_parts.append(f"fade=t=out:st={duracao - fade_duration}:d={fade_duration}")

    video_filter = ",".join(vf_parts)

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(inicio_seg),
        "-to", str(fim_seg),
        "-i", caminho_video,
        "-vf", video_filter,
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

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            print(f"  [ZOOM] ffmpeg error: {result.stderr[-300:]}")
            return False
        return True
    except Exception as e:
        print(f"  [ZOOM] erro: {e}")
        return False


def _build_zoompan(keyframes, orig_w, orig_h, target_w, target_h, fps, duracao):
    if not keyframes:
        return f"scale={target_w}:{target_h}"

    n_frames = int(duracao * fps)

    crop_w = keyframes[0]["crop_w"]
    crop_h = keyframes[0]["crop_h"]

    scale_x = orig_w / crop_w
    scale_y = orig_h / crop_h

    positions = []
    for kf in keyframes:
        frame_idx = int((kf["tempo"] - keyframes[0]["tempo"]) * fps)
        x_pct = kf["x"] / max(orig_w - crop_w, 1)
        y_pct = kf["y"] / max(orig_h - crop_h, 1)
        positions.append((frame_idx, x_pct, y_pct))

    if len(positions) == 1:
        x_pct = positions[0][1]
        y_pct = positions[0][2]
        return (
            f"crop={crop_w}:{crop_h}:"
            f"{int(x_pct * (orig_w - crop_w))}:{int(y_pct * (orig_h - crop_h))},"
            f"scale={target_w}:{target_h}"
        )

    return (
        f"crop={crop_w}:{crop_h}:"
        f"{int(positions[0][1] * (orig_w - crop_w))}:{int(positions[0][2] * (orig_h - crop_h))},"
        f"scale={target_w}:{target_h}"
    )


def aplicar_fade(caminho_video, caminho_saida, duracao=0.3):
    probe = _probe_video(caminho_video)
    video_dur = float(probe.get("duration", 0))
    if video_dur <= 0:
        return False

    cmd = [
        "ffmpeg", "-y",
        "-i", caminho_video,
        "-vf", f"fade=t=in:st=0:d={duracao},fade=t=out:st={video_dur - duracao}:d={duracao}",
        "-af", f"afade=t=in:st=0:d={duracao},afade=t=out:st={video_dur - duracao}:d={duracao}",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "192k",
        "-movflags", "+faststart",
        "-threads", "4",
        caminho_saida,
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return result.returncode == 0
    except Exception:
        return False


def _probe_video(caminho):
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error",
             "-show_entries", "format=duration:stream=width,height",
             "-of", "csv=p=0", caminho],
            capture_output=True, text=True, timeout=10,
        )
        info = {}
        for line in result.stdout.strip().split("\n"):
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
