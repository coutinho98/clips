"""
Speaker Diarizer — identifica quem esta falando no audio. 100% local.

Usa MFCC + delta features + clustering espectral para agrupar segments por speaker.
Sem modelos externos, sem tokens, sem API. Tudo roda na maquina local.

Retorna uma timeline de segments: [{start, end, speaker}, ...]
"""

import os
import subprocess
import tempfile
import numpy as np

try:
    import torchaudio
    import torch
    _HAS_TORCHAUDIO = True
except ImportError:
    _HAS_TORCHAUDIO = False

try:
    from sklearn.cluster import AgglomerativeClustering
    from sklearn.metrics import silhouette_score
    _HAS_SKLEARN = True
except ImportError:
    _HAS_SKLEARN = False


def _extrair_audio(caminho_video, inicio_seg, fim_seg):
    """Extrai audio do segmento de video como WAV 16kHz mono."""
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False, dir="/tmp")
    tmp.close()
    cmd = [
        "ffmpeg", "-y", "-v", "quiet",
        "-ss", str(inicio_seg), "-to", str(fim_seg),
        "-i", caminho_video,
        "-vn", "-ac", "1", "-ar", "16000",
        "-f", "wav", tmp.name,
    ]
    subprocess.run(cmd, capture_output=True, timeout=60)
    if not os.path.exists(tmp.name) or os.path.getsize(tmp.name) < 100:
        return None
    return tmp.name


def diarizar(caminho_video, inicio_seg, fim_seg, num_speakers=None):
    """
    Executa diarizacao de speakers no segmento de audio. 100% local.

    Retorna: lista de {start, end, speaker} (timestamps relativos ao inicio)
             ou None se falhar.
    """
    if not _HAS_TORCHAUDIO or not _HAS_SKLEARN:
        return None

    audio_path = _extrair_audio(caminho_video, inicio_seg, fim_seg)
    if not audio_path:
        return None

    try:
        return _diarizar_local(audio_path, num_speakers)
    except Exception as e:
        print(f"  [DIARIZACAO] Erro: {e}")
        return None
    finally:
        try:
            os.unlink(audio_path)
        except OSError:
            pass


def _computar_mfcc(audio_path, n_mfcc=13):
    """Carrega audio e computa MFCC + delta features (sem delta-delta, menos ruido)."""
    waveform, sample_rate = torchaudio.load(audio_path)

    hop_length = 160

    mfcc_transform = torchaudio.transforms.MFCC(
        sample_rate=sample_rate,
        n_mfcc=n_mfcc,
        melkwargs={"n_fft": 512, "hop_length": hop_length, "n_mels": 40},
    )
    mfcc = mfcc_transform(waveform).squeeze(0)

    delta = torchaudio.functional.compute_deltas(mfcc)

    features = torch.cat([mfcc, delta], dim=0).numpy()

    waveform_np = waveform[0].numpy()
    return features, waveform_np, sample_rate, hop_length


def _vad_energia(waveform_np, sample_rate, hop_length, mfcc_frames,
                 threshold_db=-35.0, min_frames=3):
    """
    Voice Activity Detection baseado em energia.
    Retorna mascara booleana indicando quais frames MFCC tem fala.
    """
    frame_size = hop_length
    n_frames = min(mfcc_frames, len(waveform_np) // frame_size)

    energies = []
    for i in range(n_frames):
        start = i * frame_size
        end = min(start + frame_size, len(waveform_np))
        if end <= start:
            energies.append(-100)
            continue
        frame = waveform_np[start:end].astype(np.float64)
        rms = np.sqrt(np.mean(frame ** 2)) + 1e-10
        db = 20 * np.log10(rms)
        energies.append(db)

    energies = np.array(energies)
    threshold = max(threshold_db, np.percentile(energies, 20))

    mask = energies > threshold

    for i in range(1, len(mask) - 1):
        if not mask[i] and mask[i - 1] and mask[i + 1]:
            mask[i] = True

    active_count = 0
    for i in range(len(mask)):
        if mask[i]:
            active_count += 1
            if active_count < min_frames:
                mask[i] = False
        else:
            if active_count < min_frames:
                for j in range(active_count):
                    mask[i - 1 - j] = False
            active_count = 0

    return mask


def _diarizar_local(audio_path, num_speakers=None, window_sec=1.5, hop_sec=0.75):
    """
    Diarizacao local: MFCC+delta features + VAD + clustering.

    Pipeline:
    1. Computa MFCC + delta
    2. VAD por energia para filtrar silencio
    3. Extrai features por janela deslizante
    4. Clustering para agrupar speakers
    5. Merge de segments consecutivos
    """
    features_all, waveform_np, sample_rate, hop_length = _computar_mfcc(audio_path)
    mfcc_fps = sample_rate / hop_length
    total_frames = features_all.shape[1]
    duracao = len(waveform_np) / sample_rate

    if duracao < 2.0 or total_frames < 20:
        return None

    vad_mask = _vad_energia(waveform_np, sample_rate, hop_length, total_frames)

    win_frames = int(window_sec * mfcc_fps)
    hop_frames = int(hop_sec * mfcc_fps)

    feat_list = []
    timestamps = []

    pos = 0
    while pos + win_frames < total_frames:
        win_slice = slice(pos, pos + win_frames)
        active_ratio = np.mean(vad_mask[win_slice]) if np.any(vad_mask[win_slice]) else 0

        if active_ratio < 0.3:
            pos += hop_frames
            continue

        segment = features_all[:, win_slice]

        active_mask = vad_mask[win_slice]
        if np.any(active_mask):
            segment_active = segment[:, active_mask]
            mean_feat = np.mean(segment_active, axis=1) if segment_active.shape[1] > 0 else np.mean(segment, axis=1)
        else:
            mean_feat = np.mean(segment, axis=1)

        feat_list.append(mean_feat)
        t_start = pos / mfcc_fps
        t_end = (pos + win_frames) / mfcc_fps
        timestamps.append((t_start, t_end))

        pos += hop_frames

    if len(feat_list) < 4:
        return None

    X = np.array(feat_list)

    from sklearn.preprocessing import StandardScaler
    scaler = StandardScaler()
    X = scaler.fit_transform(X)

    n_sp = num_speakers
    if n_sp is None:
        max_sp = 4 if duracao < 60 else 6
        n_sp = _estimate_num_speakers(X, max_n=max_sp)

    labels = AgglomerativeClustering(
        n_clusters=n_sp, metric="cosine", linkage="average"
    ).fit_predict(X)

    labels, n_sp = _merge_similar_clusters(X, labels, threshold=0.82)

    labels = AgglomerativeClustering(
        n_clusters=n_sp, metric="cosine", linkage="average"
    ).fit_predict(X)

    segments = []
    for i, (start, end) in enumerate(timestamps):
        segments.append({
            "start": float(start),
            "end": float(end),
            "speaker": f"SPEAKER_{labels[i]:02d}",
        })

    segments = _merge_speaker_segments(segments)
    segments = _filtrar_curtos(segments, min_dur=0.5)
    segments = _relabel_speakers(segments)

    n_final = len(set(s["speaker"] for s in segments))
    print(f"  [DIARIZACAO] Local MFCC: {len(segments)} segments, {n_final} speakers")
    return segments


def _estimate_num_speakers(X, min_n=2, max_n=6, penalty=0.08):
    """
    Estima numero de speakers usando silhouette score com penalizacao BIC-like.
    penalty: custo por cluster adicional (reduz over-segmentation).
    """
    if len(X) < min_n * 2:
        return min_n

    best_n = min_n
    best_score = -1

    upper = min(max_n, len(X) - 1)
    for n in range(min_n, upper + 1):
        labels = AgglomerativeClustering(
            n_clusters=n, metric="cosine", linkage="average"
        ).fit_predict(X)
        raw_score = silhouette_score(X, labels, metric="cosine")
        penalized = raw_score - penalty * (n - min_n)
        if penalized > best_score:
            best_score = penalized
            best_n = n

    return best_n


def _merge_similar_clusters(X, labels, threshold=0.82):
    """
    Merge clusters cujos centroides tem similaridade cosseno > threshold.
    Retorna (novos_labels, novo_n_clusters).
    """
    unique = sorted(set(labels))
    if len(unique) <= 1:
        return labels, len(unique)

    centroids = {}
    for c in unique:
        mask = labels == c
        centroids[c] = np.mean(X[mask], axis=0)

    parent = {c: c for c in unique}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i in range(len(unique)):
        for j in range(i + 1, len(unique)):
            c1, c2 = unique[i], unique[j]
            cos_sim = float(np.dot(centroids[c1], centroids[c2]) /
                            (np.linalg.norm(centroids[c1]) * np.linalg.norm(centroids[c2]) + 1e-10))
            if cos_sim > threshold:
                root1, root2 = find(c1), find(c2)
                if root1 != root2:
                    parent[root2] = root1

    remap = {}
    next_id = 0
    for c in unique:
        root = find(c)
        if root not in remap:
            remap[root] = next_id
            next_id += 1
        remap[c] = remap[root]

    new_labels = np.array([remap[l] for l in labels])
    return new_labels, next_id


def _merge_speaker_segments(segments, gap_threshold=0.5):
    """Merge segments consecutivos do mesmo speaker."""
    if not segments:
        return segments

    merged = [dict(segments[0])]
    for seg in segments[1:]:
        last = merged[-1]
        if seg["speaker"] == last["speaker"] and seg["start"] - last["end"] < gap_threshold:
            last["end"] = seg["end"]
        else:
            merged.append(dict(seg))

    return merged


def _filtrar_curtos(segments, min_dur=0.5):
    """Remove segments muito curtos, atribuindo ao speaker anterior."""
    if not segments:
        return segments

    result = []
    for seg in segments:
        if seg["end"] - seg["start"] < min_dur and result:
            result[-1]["end"] = seg["end"]
        else:
            result.append(dict(seg))

    return result


def _relabel_speakers(segments):
    """Relabel speakers em ordem de primeira aparicao (SPEAKER_00, 01, ...)."""
    if not segments:
        return segments

    label_map = {}
    next_id = 0
    for seg in segments:
        sp = seg["speaker"]
        if sp not in label_map:
            label_map[sp] = f"SPEAKER_{next_id:02d}"
            next_id += 1
        seg["speaker"] = label_map[sp]

    return segments


def mapear_speakers_visuais(diarizacao, speaker_timeline_visual):
    """
    Mapeia speakers do audio para IDs visuais do tracking YOLOv8.

    diarizacao: [{start, end, speaker}] do audio
    speaker_timeline_visual: [{tempo, active_speaker, tracks}] do tracking

    Retorna: {speaker_audio: tid_visual} e coincidencias para debug
    """
    if not diarizacao or not speaker_timeline_visual:
        return {}, {}

    from collections import defaultdict
    coincidencias = defaultdict(lambda: defaultdict(int))

    for seg in diarizacao:
        audio_speaker = seg["speaker"]
        for entry in speaker_timeline_visual:
            t = entry["tempo"]
            if seg["start"] <= t <= seg["end"]:
                visual_tid = entry.get("active_speaker")
                if visual_tid is not None:
                    coincidencias[audio_speaker][visual_tid] += 1

    mapeamento = {}
    used_visuals = set()
    for audio_sp in sorted(coincidencias.keys()):
        votes = coincidencias[audio_sp]
        available = {k: v for k, v in votes.items() if k not in used_visuals}
        if not available:
            available = votes
        if available:
            best_visual = max(available, key=available.get)
            mapeamento[audio_sp] = best_visual
            used_visuals.add(best_visual)

    return mapeamento, dict(coincidencias)
