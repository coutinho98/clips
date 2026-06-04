import os
import subprocess
from config import PASTA_TEMP


def baixar_live(url, qualidade=None, pasta_saida=None):
    if pasta_saida is None:
        pasta_saida = PASTA_TEMP

    os.makedirs(pasta_saida, exist_ok=True)

    video_id = url.split("/")[-1].replace("=", "").replace("?", "").replace("&", "")[:40] if url else "video"
    saida_template = os.path.join(pasta_saida, f"live_{video_id}.%(ext)s")

    if qualidade is None:
        qualidade = (
            "bestvideo[height<=?2160][ext=mp4]+bestaudio[ext=m4a]/"
            "bestvideo[height<=?2160]+bestaudio/"
            "bestvideo+bestaudio/"
            "best"
        )

    cmd = [
        "yt-dlp",
        "-f", qualidade,
        "-o", saida_template,
        "--no-playlist",
        "--merge-output-format", "mp4",
        "--progress",
        "--concurrent-fragments", "4",
        "--throttled-rate", "100K",
        url,
    ]

    print(f"  Baixando live (melhor qualidade): {url}")

    try:
        resultado = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)

        if resultado.returncode != 0:
            print(f"  [AVISO] Tentando formato alternativo...")
            cmd_fallback = [
                "yt-dlp",
                "-f", "best",
                "-o", saida_template,
                "--no-playlist",
                "--merge-output-format", "mp4",
                "--progress",
                url,
            ]
            resultado = subprocess.run(cmd_fallback, capture_output=True, text=True, timeout=7200)
            if resultado.returncode != 0:
                print(f"  [ERRO] yt-dlp falhou: {resultado.stderr}")
                return None

        for f in os.listdir(pasta_saida):
            if f.startswith(f"live_{video_id}.") and f.endswith(".mp4"):
                caminho = os.path.join(pasta_saida, f)
                tamanho_mb = os.path.getsize(caminho) / (1024 * 1024)

                probe = subprocess.run(
                    ["ffprobe", "-v", "error", "-show_entries",
                     "stream=width,height,codec_name", "-of", "csv=p=0", caminho],
                    capture_output=True, text=True,
                )
                print(f"  Download concluído: {tamanho_mb:.1f} MB")
                print(f"  Info: {probe.stdout.strip()}")
                return caminho

        print("  [ERRO] Arquivo de vídeo não encontrado após download")
        return None
    except FileNotFoundError:
        print("  [ERRO] yt-dlp não encontrado. Instale com: pip install yt-dlp")
        return None
    except subprocess.TimeoutExpired:
        print("  [ERRO] Timeout no download (excedeu 2 horas)")
        return None


def baixar_audio_live(url, pasta_saida=None):
    if pasta_saida is None:
        pasta_saida = PASTA_TEMP

    os.makedirs(pasta_saida, exist_ok=True)

    saida_template = os.path.join(pasta_saida, "live_audio.%(ext)s")

    cmd = [
        "yt-dlp",
        "-f", "bestaudio",
        "-x", "--audio-format", "mp3",
        "--audio-quality", "0",
        "-o", saida_template,
        "--no-playlist",
        "--concurrent-fragments", "4",
        url,
    ]

    print(f"  Extraindo áudio da live: {url}")

    try:
        resultado = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)

        if resultado.returncode != 0:
            print(f"  [ERRO] yt-dlp falhou: {resultado.stderr}")
            return None

        for f in os.listdir(pasta_saida):
            if f.startswith("live_audio.") and f.endswith(".mp3"):
                caminho = os.path.join(pasta_saida, f)
                tamanho_mb = os.path.getsize(caminho) / (1024 * 1024)
                print(f"  Áudio extraído: {caminho} ({tamanho_mb:.1f} MB)")
                return caminho

        return None
    except FileNotFoundError:
        print("  [ERRO] yt-dlp não encontrado. Instale com: pip install yt-dlp")
        return None
