import os
import subprocess
import numpy as np
from pydub import AudioSegment
from config import PASTA_TEMP


def extrair_audio_do_video(caminho_video, pasta_saida=None):
    if pasta_saida is None:
        pasta_saida = PASTA_TEMP

    os.makedirs(pasta_saida, exist_ok=True)
    caminho_audio = os.path.join(pasta_saida, "audio_extraido.wav")

    print(f"  Extraindo áudio do vídeo (via ffmpeg)...")

    cmd = [
        "ffmpeg", "-y",
        "-i", caminho_video,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        caminho_audio,
    ]

    try:
        resultado = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if resultado.returncode != 0:
            print(f"  [ERRO FFmpeg] {resultado.stderr[-500:]}")
            return None
    except subprocess.TimeoutExpired:
        print("  [ERRO] Timeout ao extrair áudio")
        return None
    except FileNotFoundError:
        print("  [ERRO] ffmpeg não encontrado. Instale com: sudo apt install ffmpeg")
        return None

    if not os.path.exists(caminho_audio):
        print("  [ERRO] Arquivo de áudio não foi criado")
        return None

    tamanho_mb = os.path.getsize(caminho_audio) / (1024 * 1024)

    duracao_seg = 0
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", caminho_audio],
            capture_output=True, text=True,
        )
        duracao_seg = float(probe.stdout.strip())
    except Exception:
        pass

    print(f"  Áudio extraído: {duracao_seg:.1f}s ({duracao_seg / 60:.1f} min) ({tamanho_mb:.1f} MB)")
    return caminho_audio


def analisar_picos_energia(caminho_audio, janela_ms=2000, threshold_sigma=1.5):
    print(f"  Analisando picos de energia no áudio...")

    audio = AudioSegment.from_file(caminho_audio)
    audio = audio.set_channels(1)

    duracao_ms = len(audio)
    n_janelas = duracao_ms // janela_ms

    energias = []
    for i in range(n_janelas):
        inicio = i * janela_ms
        fim = inicio + janela_ms
        segmento = audio[inicio:fim]

        samples = np.array(segmento.get_array_of_samples(), dtype=np.float64)
        if len(samples) == 0:
            energias.append(0)
            continue

        rms = np.sqrt(np.mean(samples ** 2))
        energias.append(rms)

    energias = np.array(energias)

    media = np.mean(energias)
    desvio = np.std(energias)
    limite = media + (desvio * threshold_sigma)

    picos = []
    acima = energias > limite

    i = 0
    while i < len(acima):
        if acima[i]:
            inicio_janela = i
            while i < len(acima) and acima[i]:
                i += 1
            fim_janela = i

            pico_inicio_ms = inicio_janela * janela_ms
            pico_fim_ms = fim_janela * janela_ms

            energia_pico = np.max(energias[inicio_janela:fim_janela])
            energia_rel = (energia_pico - media) / max(desvio, 1)

            picos.append({
                "inicio_ms": pico_inicio_ms,
                "fim_ms": pico_fim_ms,
                "inicio_seg": pico_inicio_ms / 1000.0,
                "fim_seg": pico_fim_ms / 1000.0,
                "energia_rms": float(energia_pico),
                "energia_relacionada": float(energia_rel),
            })
        else:
            i += 1

    picos.sort(key=lambda x: x["energia_relacionada"], reverse=True)

    print(f"  Encontrados {len(picos)} picos de energia (threshold: {threshold_sigma} sigma)")
    return picos


def analisar_silencios(caminho_audio, silencio_db=-40, min_silencio_ms=1000):
    print(f"  Detectando silêncios...")

    audio = AudioSegment.from_file(caminho_audio)
    audio = audio.set_channels(1)

    janela_ms = 100
    n_janelas = len(audio) // janela_ms

    silencios = []
    inicio_silencio = None

    for i in range(n_janelas):
        segmento = audio[i * janela_ms:(i + 1) * janela_ms]
        if segmento.dBFS < silencio_db:
            if inicio_silencio is None:
                inicio_silencio = i * janela_ms
        else:
            if inicio_silencio is not None:
                duracao = i * janela_ms - inicio_silencio
                if duracao >= min_silencio_ms:
                    silencios.append({
                        "inicio_ms": inicio_silencio,
                        "fim_ms": i * janela_ms,
                        "duracao_ms": duracao,
                    })
                inicio_silencio = None

    if inicio_silencio is not None:
        duracao = n_janelas * janela_ms - inicio_silencio
        if duracao >= min_silencio_ms:
            silencios.append({
                "inicio_ms": inicio_silencio,
                "fim_ms": n_janelas * janela_ms,
                "duracao_ms": duracao,
            })

    print(f"  Encontrados {len(silencios)} trechos de silêncio")
    return silencios


def detectar_momentos_interessantes(caminho_audio, duracao_corte_min=30, duracao_corte_max=90):
    picos = analisar_picos_energia(caminho_audio, janela_ms=2000, threshold_sigma=1.5)

    momentos = []
    for pico in picos:
        centro = (pico["inicio_seg"] + pico["fim_seg"]) / 2.0
        inicio = max(0, centro - duracao_corte_max / 2.0)
        fim = centro + duracao_corte_max / 2.0

        momentos.append({
            "inicio_seg": inicio,
            "fim_seg": fim,
            "score": pico["energia_relacionada"],
            "tipo": "audio_peak",
        })

    momentos = _remover_sobreposicao(momentos, distancia_minima=duracao_corte_min)

    print(f"  {len(momentos)} momentos candidatos após remoção de sobreposição")
    return momentos


def _remover_sobreposicao(momentos, distancia_minima=30):
    if not momentos:
        return momentos

    momentos.sort(key=lambda x: x["inicio_seg"])

    resultado = [momentos[0]]
    for m in momentos[1:]:
        ultimo = resultado[-1]
        if m["inicio_seg"] - ultimo["inicio_seg"] >= distancia_minima:
            resultado.append(m)

    return resultado
