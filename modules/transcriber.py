import os
import re
import json
import subprocess
from config import PASTA_TEMP, OPENAI_API_KEY, WHISPER_INITIAL_PROMPT


def _detectar_device():
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda", "float16"
    except ImportError:
        pass
    return "cpu", "int8"


def transcrever_com_faster_whisper(caminho_audio, modelo="medium", idioma="pt"):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("  [!] faster-whisper não instalado, tentando whisper normal...")
        return transcrever_com_whisper_local(caminho_audio, modelo, idioma)

    device, compute_type = _detectar_device()
    print(f"  Carregando faster-whisper '{modelo}' (device={device}, compute={compute_type})...")
    try:
        model = WhisperModel(modelo, device=device, compute_type=compute_type)
    except Exception:
        print(f"  [!] Falhou com {compute_type}, tentando auto...")
        model = WhisperModel(modelo, device="cpu", compute_type="auto")

    print(f"  Transcrevendo áudio (faster-whisper)...")
    segments_iter, info = model.transcribe(
        caminho_audio,
        language=idioma,
        word_timestamps=True,
        vad_filter=True,
        vad_parameters=dict(
            min_silence_duration_ms=500,
            speech_pad_ms=200,
        ),
        initial_prompt=WHISPER_INITIAL_PROMPT,
        condition_on_previous_text=True,
        compression_ratio_threshold=2.4,
        no_speech_threshold=0.3,
        beam_size=5,
        best_of=5,
    )

    segmentos = []
    for seg in segments_iter:
        texto = seg.text.strip()
        if not texto:
            continue
        words_data = []
        if seg.words:
            for w in seg.words:
                words_data.append({
                    "inicio": w.start,
                    "fim": w.end,
                    "texto": w.word.strip(),
                    "probabilidade": getattr(w, "probability", None),
                })
        segmentos.append({
            "inicio": seg.start,
            "fim": seg.end,
            "texto": texto,
            "words": words_data,
        })

    texto_completo = " ".join(s["texto"] for s in segmentos)
    duracao = segmentos[-1]["fim"] if segmentos else 0

    print(f"  Transcrição concluída: {len(segmentos)} segmentos, {duracao:.1f}s ({duracao/60:.1f} min)")
    return {
        "texto_completo": texto_completo,
        "segmentos": segmentos,
        "duracao": duracao,
        "idioma": idioma,
    }


def transcrever_com_whisper_local(caminho_audio, modelo="medium", idioma="pt"):
    try:
        import whisper
    except ImportError:
        print("  [ERRO] whisper não instalado. Use: pip install openai-whisper")
        return None

    print(f"  Carregando modelo Whisper '{modelo}'...")
    model = whisper.load_model(modelo)

    print(f"  Transcrevendo áudio...")
    resultado = model.transcribe(
        caminho_audio,
        language=idioma,
        verbose=False,
        word_timestamps=True,
        initial_prompt=WHISPER_INITIAL_PROMPT,
        beam_size=5,
        best_of=5,
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

    print(f"  Transcrição concluída: {len(segmentos)} segmentos, {duracao:.1f}s")
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
    print(f"  Transcrição API concluída: {len(segmentos)} segmentos, {duracao:.1f}s")
    return {
        "texto_completo": texto,
        "segmentos": segmentos,
        "duracao": duracao,
        "idioma": idioma,
    }


def transcrever_audio(caminho_audio, metodo="local", modelo="medium", idioma="pt",
                      corrigir_com_ia=False):
    print(f"\n  [Transcrição] Método: {metodo}, Modelo: {modelo}")

    if modelo == "parakeet" or metodo == "parakeet":
        from modules.parakeet_transcriber import transcrever_com_parakeet
        transcricao = transcrever_com_parakeet(caminho_audio, idioma)
    elif metodo == "api":
        transcricao = transcrever_com_whisper_api(caminho_audio, idioma)
    elif metodo == "local":
        transcricao = None
        try:
            transcricao = transcrever_com_whisper_cpp(caminho_audio, modelo, idioma)
        except Exception:
            pass
        if not transcricao:
            try:
                from faster_whisper import WhisperModel
                transcricao = transcrever_com_faster_whisper(caminho_audio, modelo, idioma)
            except ImportError:
                transcricao = transcrever_com_whisper_local(caminho_audio, modelo, idioma)
    else:
        print(f"  [ERRO] Método desconhecido: {metodo}. Use 'local' ou 'api'")
        return None

    if transcricao:
        transcricao = filtrar_e_limpar_segmentos(transcricao)
        if corrigir_com_ia:
            transcricao = corrigir_transcricao(transcricao)

    return transcricao


def transcrever_com_whisper_cpp(caminho_audio, modelo="small", idioma="pt"):
    import tempfile

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cli_path = os.path.join(base_dir, "whisper-cpp", "bin", "whisper-cli")
    model_path = os.path.join(base_dir, "whisper-cpp", "models", f"ggml-{modelo}.bin")

    if not os.path.exists(cli_path):
        return None
    if not os.path.exists(model_path):
        print(f"  [!] Modelo whisper.cpp não encontrado: {model_path}")
        return None

    threads = os.cpu_count() or 4

    tmp_out = tempfile.mktemp(suffix=".json")
    cmd = [
        cli_path,
        "-m", model_path,
        "-l", idioma,
        "-t", str(threads),
        "-bs", "5",
        "-bo", "5",
        "-sow",
        "--max-len", "42",
        "-ojf",
        "-of", tmp_out,
        caminho_audio,
    ]

    print(f"  Transcrevendo com whisper.cpp ({modelo}, {threads} threads)...")
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    if proc.returncode != 0:
        print(f"  [!] whisper.cpp falhou: {proc.stderr[-300:]}")
        return None

    json_path = tmp_out + ".json"
    if not os.path.exists(json_path):
        return None

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    os.remove(json_path)

    segmentos = []
    for seg_data in data.get("transcription", []):
        texto = seg_data.get("text", "").strip()
        if not texto:
            continue

        inicio_ms = seg_data.get("offsets", {}).get("from", 0)
        fim_ms = seg_data.get("offsets", {}).get("to", 0)

        words_data = []
        for tok in seg_data.get("tokens", []):
            tok_text = tok.get("text", "").strip()
            if not tok_text or tok_text.startswith("["):
                continue
            w_from = tok.get("offsets", {}).get("from", 0)
            w_to = tok.get("offsets", {}).get("to", 0)
            prob = tok.get("p", 0)
            if w_to > w_from:
                words_data.append({
                    "inicio": w_from / 1000.0,
                    "fim": w_to / 1000.0,
                    "texto": tok_text,
                    "probabilidade": prob,
                })

        segmentos.append({
            "inicio": inicio_ms / 1000.0,
            "fim": fim_ms / 1000.0,
            "texto": texto,
            "words": words_data,
        })

    duracao = segmentos[-1]["fim"] if segmentos else 0
    texto_completo = " ".join(s["texto"] for s in segmentos)

    print(f"  Transcrição concluída: {len(segmentos)} segmentos, {duracao:.1f}s")
    return {
        "texto_completo": texto_completo,
        "segmentos": segmentos,
        "duracao": duracao,
        "idioma": idioma,
    }


PROMPT_CORRECAO = """Você é um corretor especialista em legendas de vídeos em português brasileiro.
Corrija os segmentos de transcrição abaixo.

Regras OBRIGATÓRIAS:
- Corrija erros de ortografia e palavras mal transcritas (ex: "latidianzão" -> "escritório", "pântida" -> "definida")
- REMOVA pontos finais, vírgulas e pontuação de frases incompletas ou fragmentos curtos
- REMOVA segmentos completamente ininteligíveis ou sem sentido (deixe vazio: [índice] )
- NÃO adicione pontuação onde não existe pausa natural na fala
- Mantenha gírias, palavrões e expressões informais EXATAMENTE como são falados
- Mantenha o tom informal e coloquial
- NÃO adicione palavras que não estão no áudio
- NÃO mude a ordem ou estrutura das frases
- Se um segmento é só ruído ou ininteligível, retorne vazio
- Retorne NO MESMO formato [índice] texto corrigido, um por linha

Exemplos:
Entrada: [0] Nego está.
Saída: [0] Nego tá

Entrada: [1] Não é bem.
Saída: [1] 

Entrada: [2] Camiando milk my egg.
Saída: [2] 

Entrada: [3] Tá fazendo uma musculação.
Saída: [3] Tá fazendo musculação

Textos para corrigir:"""


def corrigir_transcricao(transcricao):
    import requests
    from concurrent.futures import ThreadPoolExecutor, as_completed

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
        print("  [!] Sem IA disponível para corrigir transcrição, usando original")
        return transcricao

    provedor = "Ollama" if usar_ollama else "OpenAI"
    print(f"  Corrigindo transcrição com {provedor} ({len(segmentos)} segmentos)...")

    batch_size = 10
    batches = []
    for i in range(0, len(segmentos), batch_size):
        batches.append((i, segmentos[i:i + batch_size]))

    def _corrigir_batch(batch_info):
        i, batch = batch_info
        textos = []
        for j, seg in enumerate(batch):
            texto = seg["texto"].strip()
            if texto and len(texto) > 1:
                textos.append(f"[{j}] {texto}")

        if not textos:
            return 0

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
                from openai import OpenAI
                client = OpenAI(api_key=OPENAI_API_KEY)
                resposta = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": PROMPT_CORRECAO},
                        {"role": "user", "content": bloco},
                    ],
                    temperature=0.1,
                    max_tokens=1500,
                )
                correcao = resposta.choices[0].message.content.strip()

            corrigidos = 0
            linhas = correcao.strip().split("\n")
            for linha in linhas:
                linha = linha.strip()
                if not linha or not linha.startswith("["):
                    continue
                try:
                    idx_fim = linha.index("]")
                    idx = int(linha[1:idx_fim])
                    texto_corrigido = linha[idx_fim + 1:].strip()
                    if idx < len(batch):
                        if texto_corrigido:
                            batch[idx]["texto"] = texto_corrigido
                            corrigidos += 1
                        else:
                            batch[idx]["texto"] = ""
                            corrigidos += 1
                except (ValueError, IndexError):
                    continue
            return corrigidos

        except Exception:
            return 0

    corrigidos = 0
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(_corrigir_batch, b): b[0] for b in batches}
        for future in as_completed(futures):
            corrigidos += future.result()

    segmentos = [s for s in segmentos if s["texto"].strip()]

    transcricao["segmentos"] = segmentos
    transcricao["texto_completo"] = " ".join(s["texto"].strip() for s in segmentos)
    print(f"  {corrigidos}/{len(segmentos)} segmentos corrigidos")
    return transcricao


def filtrar_e_limpar_segmentos(transcricao):
    segmentos = transcricao.get("segmentos", [])
    if not segmentos:
        return transcricao

    print(f"  Limpando {len(segmentos)} segmentos...")

    segmentos = _filtrar_por_confianca(segmentos, threshold=0.20)
    segmentos = _remover_duplicatas_consecutivas(segmentos)
    segmentos = _limpar_pontuacao_segmentos(segmentos)
    segmentos = _remover_segmentos_curto_lixo(segmentos)

    transcricao["segmentos"] = segmentos
    transcricao["texto_completo"] = " ".join(s["texto"].strip() for s in segmentos if s["texto"].strip())

    print(f"  Após limpeza: {len(segmentos)} segmentos válidos")
    return transcricao


def _filtrar_por_confianca(segmentos, threshold=0.20):
    filtrados = []
    for seg in segmentos:
        words = seg.get("words", [])
        if not words:
            if len(seg["texto"].strip().split()) >= 3:
                filtrados.append(seg)
            continue

        probs = []
        for w in words:
            p = w.get("probabilidade", w.get("probability", None))
            if p is not None:
                probs.append(p)

        if probs:
            media = sum(probs) / len(probs)
            if media < threshold and len(seg["texto"].strip().split()) < 4:
                continue

        filtrados.append(seg)

    removidos = len(segmentos) - len(filtrados)
    if removidos > 0:
        print(f"    Removidos {removidos} segmentos por baixa confiança")
    return filtrados


def _remover_duplicatas_consecutivas(segmentos):
    if not segmentos:
        return segmentos

    filtrados = [segmentos[0]]
    for i in range(1, len(segmentos)):
        texto_atual = re.sub(r'[^\w\s]', '', segmentos[i]["texto"].strip().lower())
        texto_anterior = re.sub(r'[^\w\s]', '', filtrados[-1]["texto"].strip().lower())

        if texto_atual != texto_anterior:
            filtrados.append(segmentos[i])

    removidos = len(segmentos) - len(filtrados)
    if removidos > 0:
        print(f"    Removidos {removidos} segmentos duplicados consecutivos")
    return filtrados


def _limpar_pontuacao_segmentos(segmentos):
    for seg in segmentos:
        texto = seg["texto"].strip()

        palavras = texto.split()
        if len(palavras) <= 3:
            if texto.endswith('.') and not _termina_frase_completa(texto):
                texto = texto[:-1].strip()

        texto = re.sub(r'\.{2,}', '...', texto)
        texto = re.sub(r'\?{2,}', '?', texto)
        texto = re.sub(r'!{2,}', '!', texto)
        texto = re.sub(r',{2,}', ',', texto)

        seg["texto"] = texto

    return segmentos


def _termina_frase_completa(texto):
    texto = texto.strip()
    if not texto:
        return False

    indicadores_frase = [
        'né', 'né?', 'tá', 'tá?', 'mano', 'mano?', 'cara', 'cara?',
        'véi', 'véi?', 'bicho', 'né', 'então', 'sabe', 'viu',
        'olha', 'po', 'pô', 'nossa', 'rapaz', 'falou',
    ]

    texto_lower = texto.rstrip('.!?,;:').strip().lower()
    for ind in indicadores_frase:
        if texto_lower.endswith(ind):
            return False

    return True


def _remover_segmentos_curto_lixo(segmentos):
    filtrados = []
    for seg in segmentos:
        texto = seg["texto"].strip()
        if not texto:
            continue

        palavras = texto.split()

        if len(palavras) == 1:
            if len(texto) <= 2:
                continue
            if texto.lower() in ('tu', 'tô', 'né', 'não', 'sim', 'ah', 'eh', 'é', 'oh',
                                  'uh', 'hm', 'hum', 'hã', 'ei', 'ow', 'aí', 'ué'):
                continue

        filtrados.append(seg)

    removidos = len(segmentos) - len(filtrados)
    if removidos > 0:
        print(f"    Removidos {removidos} segmentos lixo (curtos/sem sentido)")
    return filtrados


def limpar_palavra_legenda(palavra):
    palavra = palavra.strip()
    palavra = palavra.strip('.,;:')
    return palavra


def salvar_transcricao(transcricao, caminho_saida=None):
    if caminho_saida is None:
        caminho_saida = os.path.join(PASTA_TEMP, "transcricao.json")

    with open(caminho_saida, "w", encoding="utf-8") as f:
        json.dump(transcricao, f, ensure_ascii=False, indent=2)

    print(f"  Transcrição salva: {caminho_saida}")
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
            texto = seg['texto'].strip()
            if not texto:
                continue
            f.write(f"{i}\n")
            f.write(f"{_formatar_tempo(seg['inicio'])} --> {_formatar_tempo(seg['fim'])}\n")
            f.write(f"{texto}\n\n")

    print(f"  SRT gerado: {caminho_saida}")
    return caminho_saida
