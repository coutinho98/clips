"""
Utilidades de fade para video.

As funcoes de zoom dinamico (detectar_faces_timeline, gerar_zoompan_keyframes,
aplicar_zoom_dinamico_ffmpeg) foram removidas — substituidas por modules/smart_framer.py
que usa YOLOv8 + speaker detection para auto-framing superior.
"""

import subprocess


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
        "-c:v", "h264_nvenc",
        "-preset", "p4",
        "-cq", "23",
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
