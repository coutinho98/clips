import os
import json
from config import PASTA_TEMP, OPENAI_API_KEY


def transcrever_com_faster_whisper(caminho_audio, modelo="base", idioma="pt"):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("  [!] faster-whisper nao instalado, tentando whisper normal...")
        return transcrever_com_whisper_local(caminho_audio, modelo, idioma)

    print(f"  Carregando faster-whisper '{modelo}'...")
    try:
        model = WhisperModel(modelo, device="cpu", compute_type="int8")
    except Exception:
        model = WhisperModel(modelo, device="cpu", compute_type="auto")

    print(f"  Transcrevendo audio (faster-whisper - mais rapido)...")
    segments_iter, info = model.transcribe(
        caminho_audio,
        language=idioma,
        word_timestamps=True,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500),
    )

    segmentos = []
    for seg in segments_iter:
        segmentos.append({
            "inicio": seg.start,
            "fim": seg.end,
            "texto": seg.text.strip(),
            "words": [{"inicio": w.start, "fim": w.end, "texto": w.word} for w in seg.words] if seg.words else [],
        })

    texto_completo = " ".join(s["texto"] for s in segmentos)
    duracao = segmentos[-1]["fim"] if segmentos else 0

    print(f"  Transcricao concluida: {len(segmentos)} segmentos, {duracao:.1f}s")
    return {
        "texto_completo": texto_completo,
        "segmentos": segmentos,
        "duracao": duracao,
        "idioma": idioma,
    }


def transcrever_com_whisper_local(caminho_audio, modelo="base", idioma="pt"):
    try:
        import whisper
    except ImportError:
        print("  [ERRO] whisper nao instalado. Use: pip install openai-whisper")
        return None

    print(f"  Carregando modelo Whisper '{modelo}'...")
    model = whisper.load_model(modelo)

    print(f"  Transcrevendo audio...")
    resultado = model.transcribe(
        caminho_audio,
        language=idioma,
        verbose=False,
        word_timestamps=True,
    )

    segmentos = []
    for seg in resultado["segments"]:
        segmentos.append({
            "inicio": seg["start"],
            "fim": seg["end"],
            "texto": seg["text"].strip(),
            "words": seg.get("words", []),
        })

    texto_completo = resultado["text"].strip()
    duracao = resultado["segments"][-1]["end"] if resultado["segments"] else 0

    print(f"  Transcricao concluida: {len(segmentos)} segmentos, {duracao:.1f}s")
    return {
        "texto_completo": texto_completo,
        "segmentos": segmentos,
        "duracao": duracao,
        "idioma": resultado.get("language", idioma),
    }


def transcrever_com_whisper_api(caminho_audio, idioma="pt"):
    from openai import OpenAI

    client = OpenAI(api_key=OPENAI_API_KEY)

    print(f"  Transcrevendo via OpenAI Whisper API...")

    with open(caminho_audio, "rb") as f:
        resposta = client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            language=idioma,
            response_format="verbose_json",
            timestamp_granularities=["segment"],
        )

    texto = resposta.text
    segmentos_api = resposta.segments if hasattr(resposta, "segments") else []

    segmentos = []
    for seg in segmentos_api:
        segmentos.append({
            "inicio": seg.start,
            "fim": seg.end,
            "texto": seg.text.strip(),
        })

    duracao = segmentos[-1]["fim"] if segmentos else 0
    print(f"  Transcricao API concluida: {len(segmentos)} segmentos, {duracao:.1f}s")
    return {
        "texto_completo": texto,
        "segmentos": segmentos,
        "duracao": duracao,
        "idioma": idioma,
    }


def transcrever_audio(caminho_audio, metodo="local", modelo="base", idioma="pt"):
    print(f"\n  [Transcricao] Metodo: {metodo}")

    if metodo == "api":
        return transcrever_com_whisper_api(caminho_audio, idioma)
    elif metodo == "local":
        try:
            from faster_whisper import WhisperModel
            return transcrever_com_faster_whisper(caminho_audio, modelo, idioma)
        except ImportError:
            return transcrever_com_whisper_local(caminho_audio, modelo, idioma)
    else:
        print(f"  [ERRO] Metodo desconhecido: {metodo}. Use 'local' ou 'api'")
        return None


def salvar_transcricao(transcricao, caminho_saida=None):
    if caminho_saida is None:
        caminho_saida = os.path.join(PASTA_TEMP, "transcricao.json")

    with open(caminho_saida, "w", encoding="utf-8") as f:
        json.dump(transcricao, f, ensure_ascii=False, indent=2)

    print(f"  Transcricao salva: {caminho_saida}")
    return caminho_saida


def segmento_para_texto(segmentos, inicio_seg, fim_seg):
    trechos = []
    for seg in segmentos:
        if seg["fim"] >= inicio_seg and seg["inicio"] <= fim_seg:
            trechos.append(seg["texto"])
    return " ".join(trechos)


def gerar_srt(segmentos, caminho_saida=None):
    if caminho_saida is None:
        caminho_saida = os.path.join(PASTA_TEMP, "legendas.srt")

    def _formatar_tempo(segundos):
        h = int(segundos // 3600)
        m = int((segundos % 3600) // 60)
        s = int(segundos % 60)
        ms = int((segundos % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    with open(caminho_saida, "w", encoding="utf-8") as f:
        for i, seg in enumerate(segmentos, 1):
            f.write(f"{i}\n")
            f.write(f"{_formatar_tempo(seg['inicio'])} --> {_formatar_tempo(seg['fim'])}\n")
            f.write(f"{seg['texto']}\n\n")

    print(f"  SRT gerado: {caminho_saida}")
    return caminho_saida
