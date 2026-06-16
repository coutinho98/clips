import os
import glob
import subprocess
import tempfile

_MODELO_CACHE = None
_NEMO_GLOB = os.path.expanduser(
    "~/.cache/torch/NeMo/NeMo_*/hf_hub_cache/yuriyvnv/parakeet-tdt-0.6b-portuguese/*/parakeet-tdt-mixed_cv_synthetic_pt-seed42.nemo"
)
MODEL_ID = "yuriyvnv/parakeet-tdt-0.6b-portuguese"

CHUNK_SEG = 60
CHUNK_OVERLAP = 2


def _carregar_modelo():
    global _MODELO_CACHE
    if _MODELO_CACHE is not None:
        return _MODELO_CACHE

    import nemo.collections.asr as nemo_asr

    arquivos = glob.glob(_NEMO_GLOB)
    if arquivos:
        nemo_file = arquivos[0]
    else:
        from huggingface_hub import snapshot_download
        cache_dir = os.path.expanduser("~/.cache/torch/NeMo/hf_download")
        snapshot_download(repo_id=MODEL_ID, local_dir=cache_dir)
        nemo_file = os.path.join(cache_dir, "parakeet-tdt-mixed_cv_synthetic_pt-seed42.nemo")
        if not os.path.exists(nemo_file):
            found = glob.glob(os.path.join(cache_dir, "**/*.nemo"), recursive=True)
            if found:
                nemo_file = found[0]

    device = "cuda" if _cuda_disponivel() else "cpu"
    print(f"  Carregando Parakeet TDT PT ({device})...")
    _MODELO_CACHE = nemo_asr.models.ASRModel.restore_from(
        nemo_file, map_location=device
    )
    _MODELO_CACHE.eval()

    _MODELO_CACHE.change_attention_model(
        self_attention_model="rel_pos_local_attn",
        att_context_size=[256, 256],
    )

    if device == "cuda":
        _MODELO_CACHE = _MODELO_CACHE.half()

    return _MODELO_CACHE


def _cuda_disponivel():
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


def _converter_wav(caminho_audio):
    if caminho_audio.lower().endswith(".wav"):
        import wave
        try:
            with wave.open(caminho_audio, "r") as wf:
                if wf.getframerate() == 16000 and wf.getnchannels() == 1:
                    return caminho_audio
        except Exception:
            pass

    tmp = tempfile.mktemp(suffix=".wav")
    subprocess.run(
        ["ffmpeg", "-y", "-i", caminho_audio,
         "-ar", "16000", "-ac", "1", "-f", "wav", tmp],
        capture_output=True, timeout=300,
    )
    return tmp


def _processar_output(result):
    seg_ts = result.timestamp.get("segment", [])
    word_ts = result.timestamp.get("word", [])

    segmentos = []
    for seg in seg_ts:
        texto_seg = seg["segment"].strip()
        if not texto_seg:
            continue

        seg_inicio = seg["start"]
        seg_fim = seg["end"]

        words_data = []
        for w in word_ts:
            if w["start"] >= seg_inicio - 0.01 and w["end"] <= seg_fim + 0.01:
                words_data.append({
                    "inicio": w["start"],
                    "fim": w["end"],
                    "texto": w["word"].strip(),
                    "probabilidade": None,
                })

        if not words_data:
            for w in word_ts:
                if w["start"] >= seg_inicio - 0.1 and w["start"] < seg_fim:
                    words_data.append({
                        "inicio": w["start"],
                        "fim": w["end"],
                        "texto": w["word"].strip(),
                        "probabilidade": None,
                    })

        segmentos.append({
            "inicio": seg_inicio,
            "fim": seg_fim,
            "texto": texto_seg,
            "words": words_data,
        })

    return segmentos


def _transcrever_em_chunks(wav_path, duracao, modelo):
    num_chunks = max(1, int(duracao // CHUNK_SEG) + (1 if duracao % CHUNK_SEG > 0 else 0))
    print(f"  Parakeet: transcrevendo {duracao:.0f}s em {num_chunks} chunks de {CHUNK_SEG}s...")

    todos_segmentos = []

    for i in range(num_chunks):
        inicio_chunk = i * CHUNK_SEG
        fim_chunk = min(inicio_chunk + CHUNK_SEG + CHUNK_OVERLAP, duracao)
        dur_chunk = fim_chunk - inicio_chunk

        tmp_wav = tempfile.mktemp(suffix=".wav")
        subprocess.run(
            ["ffmpeg", "-y", "-ss", str(inicio_chunk), "-t", str(dur_chunk),
             "-i", wav_path, "-ar", "16000", "-ac", "1", "-f", "wav", tmp_wav],
            capture_output=True, timeout=60,
        )

        if not os.path.exists(tmp_wav) or os.path.getsize(tmp_wav) < 1000:
            continue

        output = modelo.transcribe([tmp_wav], timestamps=True)
        os.remove(tmp_wav)

        chunk_segs = _processar_output(output[0])

        for seg in chunk_segs:
            seg_fim_rel = seg["fim"]
            if fim_chunk < duracao and seg_fim_rel > CHUNK_SEG:
                continue

            seg["inicio"] += inicio_chunk
            seg["fim"] += inicio_chunk
            for w in seg["words"]:
                w["inicio"] += inicio_chunk
                w["fim"] += inicio_chunk
            todos_segmentos.append(seg)

        pct = (i + 1) / num_chunks * 100
        print(f"    Chunk {i+1}/{num_chunks} ({pct:.0f}%) - {len(chunk_segs)} segmentos")

    return todos_segmentos


def transcrever_com_parakeet(caminho_audio, idioma="pt"):
    import time

    wav_path = _converter_wav(caminho_audio)
    cleanup = wav_path != caminho_audio

    try:
        modelo = _carregar_modelo()
        duracao = _probe_duracao(wav_path)

        t0 = time.time()

        if duracao <= 120:
            output = modelo.transcribe([wav_path], timestamps=True)
            segmentos = _processar_output(output[0])
            texto_completo = output[0].text.strip()
        else:
            segmentos = _transcrever_em_chunks(wav_path, duracao, modelo)
            texto_completo = " ".join(s["texto"] for s in segmentos)

        elapsed = time.time() - t0
        duracao_final = segmentos[-1]["fim"] if segmentos else duracao

        print(f"  Parakeet: {len(segmentos)} segmentos, {duracao_final:.1f}s em {elapsed:.1f}s (RTF={elapsed/max(duracao_final,0.1):.2f})")

        return {
            "texto_completo": texto_completo,
            "segmentos": segmentos,
            "duracao": duracao_final,
            "idioma": idioma,
        }

    finally:
        if cleanup and os.path.exists(wav_path):
            os.remove(wav_path)


def _probe_duracao(wav_path):
    try:
        proc = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", wav_path],
            capture_output=True, text=True, timeout=10,
        )
        return float(proc.stdout.strip())
    except Exception:
        return 0.0
