import os
import re
import subprocess
from config import PASTA_TEMP


def _extrair_video_id(url):
    padroes = [
        r'(?:v=|/v/|youtu\.be/|/embed/)([a-zA-Z0-9_-]{11})',
        r'watch\?([a-zA-Z0-9_-]{11})',
    ]
    for p in padroes:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return re.sub(r'[^a-zA-Z0-9_-]', '', url.split("/")[-1])[:20]


def _obter_titulo(url):
    try:
        result = subprocess.run(
            ["yt-dlp", "--get-title", "--no-playlist", url],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return None


def _buscar_live_existente(video_id, pasta_saida):
    for f in os.listdir(pasta_saida):
        if f.startswith(f"live_{video_id}") and f.endswith(".mp4"):
            caminho = os.path.join(pasta_saida, f)
            tamanho_mb = os.path.getsize(caminho) / (1024 * 1024)
            if tamanho_mb > 10:
                print(f"  Live já existe em cache: {f} ({tamanho_mb:.1f} MB)")
                return caminho
    return None


def baixar_live(url, qualidade=None, pasta_saida=None):
    if pasta_saida is None:
        pasta_saida = PASTA_TEMP

    os.makedirs(pasta_saida, exist_ok=True)

    video_id = _extrair_video_id(url)

    existente = _buscar_live_existente(video_id, pasta_saida)
    if existente:
        titulo = _obter_titulo(url)
        return existente, titulo

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

    titulo_video = _obter_titulo(url)

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
                return None, None

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
                if titulo_video:
                    print(f"  Título: {titulo_video}")
                return caminho, titulo_video

        print("  [ERRO] Arquivo de vídeo não encontrado após download")
        return None, None
    except FileNotFoundError:
        print("  [ERRO] yt-dlp não encontrado. Instale com: pip install yt-dlp")
        return None, None
    except subprocess.TimeoutExpired:
        print("  [ERRO] Timeout no download (excedeu 2 horas)")
        return None, None


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
