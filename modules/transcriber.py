import os
import json
from config import (
    PASTA_TEMP,
    OPENAI_API_KEY,
    OPENAI_CHAT_MODEL,
    OPENAI_TRANSCRIBE_MODEL,
    criar_cliente_openai,
    nome_provedor_openai,
)


def _detectar_device():
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda", "float16"
    except ImportError:
        pass
    return "cpu", "int8"


def _erro_cuda_incompativel(exc):
    msg = str(exc).lower()
    indicadores = (
        "libcublas",
        "cublas",
        "cuda",
        "cudnn",
        "cannot be loaded",
        "unable to load",
    )
    return any(ind in msg for ind in indicadores)


def _coletar_segmentos_faster_whisper(model, caminho_audio, idioma):
    print(f"  Transcrevendo audio (faster-whisper)...")
    segments_iter, info = model.transcribe(
        caminho_audio,
        language=idioma,
        word_timestamps=True,
        vad_filter=True,
        vad_parameters=dict(
            min_silence_duration_ms=500,
            speech_pad_ms=200,
        ),
        initial_prompt="Olá, bem-vindos ao vídeo de hoje. Vamos falar sobre várias coisas interessantes e importantes. Obrigado por assistir.",
        condition_on_previous_text=True,
        compression_ratio_threshold=2.4,
        no_speech_threshold=0.6,
        beam_size=5,
        best_of=5,
    )

    segmentos = []
    for seg in segments_iter:
        texto = seg.text.strip()
        if not texto:
            continue
        segmentos.append({
            "inicio": seg.start,
            "fim": seg.end,
            "texto": texto,
            "words": [{"inicio": w.start, "fim": w.end, "texto": w.word} for w in seg.words] if seg.words else [],
        })

    return segmentos


def transcrever_com_faster_whisper(caminho_audio, modelo="small", idioma="pt"):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("  [!] faster-whisper nao instalado, tentando whisper normal...")
        return transcrever_com_whisper_local(caminho_audio, modelo, idioma)

    device, compute_type = _detectar_device()
    print(f"  Carregando faster-whisper '{modelo}' (device={device}, compute={compute_type})...")
    try:
        model = WhisperModel(modelo, device=device, compute_type=compute_type)
    except Exception:
        print(f"  [!] Falhou com {compute_type}, tentando auto...")
        model = WhisperModel(modelo, device="cpu", compute_type="auto")

    try:
        segmentos = _coletar_segmentos_faster_whisper(model, caminho_audio, idioma)
    except Exception as exc:
        if device != "cuda" or not _erro_cuda_incompativel(exc):
            raise

        print("  [!] CUDA indisponivel em tempo de execucao, refazendo em CPU...")
        model = WhisperModel(modelo, device="cpu", compute_type="auto")
        segmentos = _coletar_segmentos_faster_whisper(model, caminho_audio, idioma)

    texto_completo = " ".join(s["texto"] for s in segmentos)
    duracao = segmentos[-1]["fim"] if segmentos else 0

    print(f"  Transcricao concluida: {len(segmentos)} segmentos, {duracao:.1f}s ({duracao/60:.1f} min)")
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
    client = criar_cliente_openai()

    print(f"  Transcrevendo via {nome_provedor_openai()} ({OPENAI_TRANSCRIBE_MODEL})...")

    with open(caminho_audio, "rb") as f:
        resposta = client.audio.transcriptions.create(
            model=OPENAI_TRANSCRIBE_MODEL,
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
        transcricao = transcrever_com_whisper_api(caminho_audio, idioma)
    elif metodo == "local":
        try:
            from faster_whisper import WhisperModel
            transcricao = transcrever_com_faster_whisper(caminho_audio, modelo, idioma)
        except ImportError:
            transcricao = transcrever_com_whisper_local(caminho_audio, modelo, idioma)
    else:
        print(f"  [ERRO] Metodo desconhecido: {metodo}. Use 'local' ou 'api'")
        return None

    if transcricao:
        transcricao = corrigir_transcricao(transcricao)

    return transcricao


PROMPT_CORRECAO = """You are a Brazilian Portuguese text corrector. Fix the following transcribed text from a podcast/video.
Rules:
- Fix ONLY spelling, grammar and obvious transcription errors
- Keep the original meaning and informal tone (slang, curses, jokes are OK)
- Remove repeated filler words only if excessive (like "né né né", "tipo tipo")
- Do NOT add words that are not there
- Do NOT change the order or structure
- Return ONLY the corrected text, nothing else

Text to fix:"""


def corrigir_transcricao(transcricao):
    import requests

    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    ollama_model = os.getenv("OLLAMA_MODEL", "llama3.2")

    segmentos = transcricao.get("segmentos", [])
    if not segmentos:
        return transcricao

    usar_ollama = False
    usar_openai = False

    try:
        r = requests.get(f"{ollama_url}/api/tags", timeout=3)
        if r.status_code == 200:
            modelos = [m.get("name", "").lower() for m in r.json().get("models", [])]
            if any(ollama_model.lower() in m for m in modelos):
                usar_ollama = True
    except Exception:
        pass

    if not usar_ollama and OPENAI_API_KEY:
        usar_openai = True

    if not usar_ollama and not usar_openai:
        print("  [!] Sem IA disponivel para corrigir transcricao, usando original")
        return transcricao

    provedor = "Ollama" if usar_ollama else nome_provedor_openai()
    print(f"  Corrigindo transcricao com {provedor} ({len(segmentos)} segmentos)...")

    batch_size = 10
    corrigidos = 0

    for i in range(0, len(segmentos), batch_size):
        batch = segmentos[i:i + batch_size]
        textos = []
        for j, seg in enumerate(batch):
            texto = seg["texto"].strip()
            if texto and len(texto) > 3:
                textos.append(f"[{j}] {texto}")

        if not textos:
            continue

        bloco = "\n".join(textos)

        try:
            if usar_ollama:
                resp = requests.post(
                    f"{ollama_url}/api/chat",
                    json={
                        "model": ollama_model,
                        "messages": [
                            {"role": "system", "content": PROMPT_CORRECAO},
                            {"role": "user", "content": bloco},
                        ],
                        "stream": False,
                        "options": {"temperature": 0.1, "num_predict": 1500},
                    },
                    timeout=120,
                )
                resp.raise_for_status()
                correcao = resp.json()["message"]["content"].strip()
            else:
                client = criar_cliente_openai()
                resposta = client.chat.completions.create(
                    model=OPENAI_CHAT_MODEL,
                    messages=[
                        {"role": "system", "content": PROMPT_CORRECAO},
                        {"role": "user", "content": bloco},
                    ],
                    temperature=0.1,
                    max_tokens=1500,
                )
                correcao = resposta.choices[0].message.content.strip()

            linhas = correcao.strip().split("\n")
            for linha in linhas:
                linha = linha.strip()
                if not linha or not linha.startswith("["):
                    continue
                try:
                    idx_fim = linha.index("]")
                    idx = int(linha[1:idx_fim])
                    texto_corrigido = linha[idx_fim + 1:].strip()
                    if texto_corrigido and idx < len(batch):
                        batch[idx]["texto"] = texto_corrigido
                        corrigidos += 1
                except (ValueError, IndexError):
                    continue

        except Exception as e:
            print(f"  [!] Erro ao corrigir lote {i//batch_size}: {e}")
            continue

    transcricao["texto_completo"] = " ".join(s["texto"].strip() for s in segmentos)
    print(f"  {corrigidos}/{len(segmentos)} segmentos corrigidos")
    return transcricao


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
