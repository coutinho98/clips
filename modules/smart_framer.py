"""
Smart Framer — Auto-enquadramento inteligente para clips verticais.

Combina 3 camadas:
1. YOLOv8 + ByteTrack: rastreia pessoas com IDs persistentes
2. Active Speaker Detection: detecta quem esta falando via movimento facial
3. Diretor por categoria: aplica regras de enquadramento baseadas no tipo do corte

Gera um filtro FFmpeg de crop/zoom dinamico que segue o speaker ativo.
Substitui o antigo detectar_faces_crop (Haar Cascade) do clip_extractor.
"""

import os
import subprocess
import collections
import json
from concurrent.futures import ThreadPoolExecutor

import numpy as np

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

try:
    import torch
    if torch.cuda.is_available():
        torch.backends.cudnn.benchmark = True
    from ultralytics import YOLO
    HAS_YOLO = True
except ImportError:
    HAS_YOLO = False


_MODELO_CACHE = {}
_FACE_CASCADE = None


def _get_face_cascade():
    global _FACE_CASCADE
    if _FACE_CASCADE is None and HAS_CV2:
        _FACE_CASCADE = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
    return _FACE_CASCADE


def _detectar_rostos(frame_gray, tracks, cache=None):
    """Detecta rostos reais dentro de cada bounding box de pessoa via Haar Cascade.
    Mantem cache da ultima posicao pra evitar flicker quando a deteccao falha."""
    cascade = _get_face_cascade()
    if cascade is None or cascade.empty():
        return {}
    if cache is None:
        cache = {}

    rostos = {}
    for tid, (x1, y1, x2, y2) in tracks.items():
        bh = y2 - y1
        crop_y1 = max(0, y1)
        crop_y2 = min(frame_gray.shape[0], y1 + int(bh * 0.4))
        crop_x1 = max(0, x1)
        crop_x2 = min(frame_gray.shape[1], x2)

        detected = None
        if crop_y2 > crop_y1 and crop_x2 > crop_x1:
            region = frame_gray[crop_y1:crop_y2, crop_x1:crop_x2]
            faces = cascade.detectMultiScale(
                region, scaleFactor=1.15, minNeighbors=4, minSize=(25, 25)
            )
            if len(faces) > 0:
                fx, fy, fw, fh = max(faces, key=lambda f: f[2] * f[3])
                detected = (crop_x1 + fx, crop_y1 + fy,
                            crop_x1 + fx + fw, crop_y1 + fy + fh)

        if detected is not None:
            if tid in cache:
                old = cache[tid]
                a = 0.55
                detected = tuple(int(old[i] * (1 - a) + detected[i] * a) for i in range(4))
            cache[tid] = detected
            rostos[tid] = detected
        elif tid in cache:
            rostos[tid] = cache[tid]

    for tid in list(cache.keys()):
        if tid not in tracks:
            del cache[tid]

    return rostos

REGRAS_POR_CATEGORIA = {
    "engraçado": {
        "zoom_base": 1.0,
        "seguir_speaker": True,
        "cortar_reacao": True,
        "reaction_delay": 0.4,
        "reaction_hold": 2.0,
        "transition_speed": 0.18,
    },
    "emocionante": {
        "zoom_base": 1.0,
        "zoom_progressivo": (1.0, 1.35),
        "seguir_speaker": True,
        "transition_speed": 0.25,
    },
    "confronto": {
        "zoom_base": 0.92,
        "alternar_speakers": True,
        "seguir_speaker": True,
        "transition_speed": 0.15,
    },
    "revelação": {
        "zoom_base": 1.15,
        "seguir_speaker": True,
        "cortar_reacao": True,
        "reaction_delay": 0.3,
        "reaction_hold": 1.5,
        "transition_speed": 0.18,
    },
    "história": {
        "zoom_base": 1.1,
        "zoom_progressivo": (1.1, 1.25),
        "seguir_speaker": True,
        "transition_speed": 0.22,
    },
    "sério": {
        "zoom_base": 1.2,
        "seguir_speaker": True,
        "transition_speed": 0.22,
    },
    "eletrizante": {
        "zoom_base": 1.1,
        "cortes_rapidos": True,
        "seguir_speaker": True,
        "transition_speed": 0.12,
    },
    "polêmico": {
        "zoom_base": 1.1,
        "alternar_speakers": True,
        "seguir_speaker": True,
        "transition_speed": 0.18,
    },
}

REGRA_DEFAULT = {
    "zoom_base": 1.1,
    "seguir_speaker": True,
    "transition_speed": 0.22,
}

SPEAKER_SWITCH_COOLDOWN = 2.5
MOTION_HISTORY = 8
MIN_MOTION_THRESHOLD = 3.0
SPEAKER_MARGIN = 1.5
SUSTAINED_FRAMES = 3


def _obter_regras(categoria):
    if not categoria:
        return REGRA_DEFAULT
    cat_lower = categoria.lower().strip()
    for key, val in REGRAS_POR_CATEGORIA.items():
        if key in cat_lower or cat_lower in key:
            return val
    return REGRA_DEFAULT


def _carregar_modelo(modelo="yolov8n.pt"):
    if modelo not in _MODELO_CACHE:
        _MODELO_CACHE[modelo] = YOLO(modelo)
    return _MODELO_CACHE[modelo]


class SpeakerDetector:
    """Detecta quem esta falando via movimento da boca entre frames consecutivos."""

    def __init__(self):
        self.face_anterior = {}
        self.motion_scores = {}
        self.occluded = set()
        self.motion_history = {}
        self.active_speaker = None
        self.active_since = 0.0
        self._candidate = None
        self._candidate_count = 0

    @staticmethod
    def _mouth_rect(x1, y1, x2, y2):
        bh = y2 - y1
        bw = x2 - x1
        return (int(x1 + bw * 0.18), int(y1 + bh * 0.14),
                int(x2 - bw * 0.18), int(y1 + bh * 0.26))

    def _compute_occlusion(self, tracks):
        """Marca pessoas cujo ROI da boca esta coberto por outra pessoa a frente."""
        self.occluded = set()
        tids = list(tracks.keys())
        areas = {tid: (x2-x1)*(y2-y1) for tid, (x1, y1, x2, y2) in tracks.items()}
        for tid in tids:
            mx1, my1, mx2, my2 = self._mouth_rect(*tracks[tid])
            m_area = max(1, (mx2 - mx1) * (my2 - my1))
            for other in tids:
                if other == tid:
                    continue
                ox1, oy1, ox2, oy2 = tracks[other]
                if areas.get(other, 0) <= areas.get(tid, 0) * 0.8:
                    continue
                ix1, iy1 = max(mx1, ox1), max(my1, oy1)
                ix2, iy2 = min(mx2, ox2), min(my2, oy2)
                if ix2 > ix1 and iy2 > iy1:
                    overlap = (ix2 - ix1) * (iy2 - iy1) / m_area
                    if overlap > 0.3:
                        self.occluded.add(tid)
                        break

    def atualizar(self, tracks, frame_gray, tempo, rostos=None):
        self._compute_occlusion(tracks)

        for tid, (x1, y1, x2, y2) in tracks.items():
            if rostos and tid in rostos:
                fx1, fy1, fx2, fy2 = rostos[tid]
                fh = fy2 - fy1
                fw = fx2 - fx1
                m_x1 = max(0, fx1 + int(fw * 0.1))
                m_x2 = min(frame_gray.shape[1], fx2 - int(fw * 0.1))
                m_y1 = max(0, fy1 + int(fh * 0.55))
                m_y2 = min(frame_gray.shape[0], fy2)
            else:
                m_x1, m_y1, m_x2, m_y2 = self._mouth_rect(x1, y1, x2, y2)

            if m_x2 <= m_x1 or m_y2 <= m_y1:
                continue

            mouth_roi = frame_gray[m_y1:m_y2, m_x1:m_x2]
            mouth_roi = cv2.resize(mouth_roi, (48, 16))

            if tid in self.face_anterior:
                diff = cv2.absdiff(mouth_roi, self.face_anterior[tid])
                motion = float(np.mean(diff))
            else:
                motion = 0.0

            self.face_anterior[tid] = mouth_roi.copy()

            if tid not in self.motion_history:
                self.motion_history[tid] = collections.deque(maxlen=MOTION_HISTORY)
            self.motion_history[tid].append(motion)
            self.motion_scores[tid] = float(np.mean(self.motion_history[tid]))

        for tid in list(self.motion_scores.keys()):
            if tid not in tracks:
                del self.motion_scores[tid]
                self.face_anterior.pop(tid, None)
                self.motion_history.pop(tid, None)

        if not self.motion_scores:
            return self.active_speaker, 0.0, {}

        reliable = {tid: s for tid, s in self.motion_scores.items()
                    if tid not in self.occluded}

        if not reliable:
            return self.active_speaker, 0.0, dict(self.motion_scores)

        best_tid = max(reliable, key=reliable.get)
        best_score = reliable[best_tid]

        if best_score < MIN_MOTION_THRESHOLD:
            self._candidate = None
            self._candidate_count = 0
            return self.active_speaker, best_score, dict(self.motion_scores)

        if self.active_speaker is None:
            self.active_speaker = best_tid
            self.active_since = tempo
            self._candidate = None
            self._candidate_count = 0
        elif best_tid != self.active_speaker:
            if self.active_speaker in self.occluded:
                pass
            elif tempo - self.active_since >= SPEAKER_SWITCH_COOLDOWN:
                margin = best_score - self.motion_scores.get(self.active_speaker, 0)
                if margin > SPEAKER_MARGIN:
                    if self._candidate == best_tid:
                        self._candidate_count += 1
                    else:
                        self._candidate = best_tid
                        self._candidate_count = 1
                    if self._candidate_count >= SUSTAINED_FRAMES:
                        self.active_speaker = best_tid
                        self.active_since = tempo
                        self._candidate = None
                        self._candidate_count = 0
                else:
                    self._candidate = None
                    self._candidate_count = 0

        return self.active_speaker, best_score, dict(self.motion_scores)


def _rastrear_segmento(caminho_video, inicio_seg, fim_seg, sample_fps=4):
    """
    Processa o segmento de video e retorna:
    - timeline: lista de {tempo, active_speaker, tracks: {tid: (x1,y1,x2,y2)}, motion_scores}

    Otimizacao: FFmpeg redimensiona para 384px de altura ANTES do pipe.
    Bounding boxes sao escalonados de volta para resolucao original.
    """
    if not HAS_CV2 or not HAS_YOLO:
        return []

    model = _carregar_modelo()
    use_half = torch.cuda.is_available()

    probe_w, probe_h = _probe_dimensions(caminho_video)
    orig_w = probe_w or 1920
    orig_h = probe_h or 1080

    duracao = fim_seg - inicio_seg

    small_h = 384
    small_w = int(orig_w * small_h / orig_h / 2) * 2
    if small_w < 2:
        small_w = orig_w

    scale_x = orig_w / small_w
    scale_y = orig_h / small_h
    frame_size = small_w * small_h * 3

    cmd = [
        "ffmpeg", "-y", "-v", "quiet",
        "-ss", str(inicio_seg), "-t", str(duracao),
        "-i", caminho_video,
        "-vf", f"fps={sample_fps},scale={small_w}:{small_h}",
        "-f", "rawvideo", "-pix_fmt", "bgr24",
        "-",
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    detector = SpeakerDetector()
    rosto_cache = {}
    timeline = []
    frame_idx = 0

    try:
        while True:
            raw = proc.stdout.read(frame_size)
            if len(raw) < frame_size:
                break

            frame = np.frombuffer(raw, dtype=np.uint8).reshape((small_h, small_w, 3))
            tempo_local = frame_idx / sample_fps
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            results = model.track(
                frame, classes=[0], tracker="bytetrack.yaml",
                verbose=False, conf=0.35, persist=True,
                device=0, imgsz=384, half=use_half,
            )

            tracks_small = {}
            if results and results[0].boxes is not None and len(results[0].boxes) > 0:
                for box in results[0].boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    tid = int(box.id[0]) if box.id is not None else 0
                    tracks_small[tid] = (x1, y1, x2, y2)

            rostos = _detectar_rostos(gray, tracks_small, cache=rosto_cache)
            active_tid, score, all_scores = detector.atualizar(tracks_small, gray, tempo_local, rostos=rostos)

            tracks_orig = {
                tid: (int(x1 * scale_x), int(y1 * scale_y),
                      int(x2 * scale_x), int(y2 * scale_y))
                for tid, (x1, y1, x2, y2) in tracks_small.items()
            }

            timeline.append({
                "tempo": tempo_local,
                "active_speaker": active_tid,
                "tracks": tracks_orig,
                "motion_scores": all_scores,
                "score": score,
                "occluded": set(detector.occluded),
                "rostos": rostos,
            })
            frame_idx += 1
    finally:
        proc.stdout.close()
        proc.wait()

    return timeline


def _probe_dimensions(caminho):
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error",
             "-select_streams", "v:0",
             "-show_entries", "stream=width,height",
             "-of", "csv=p=0", caminho],
            capture_output=True, text=True, timeout=10,
        )
        parts = result.stdout.strip().split(",")
        return int(parts[0]), int(parts[1])
    except Exception:
        return 0, 0


def _probe_fps(caminho):
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error",
             "-select_streams", "v:0",
             "-show_entries", "stream=r_frame_rate",
             "-of", "csv=p=0", caminho],
            capture_output=True, text=True, timeout=10,
        )
        frac = result.stdout.strip()
        if "/" in frac:
            num, den = frac.split("/")
            return int(num) / int(den)
        return float(frac)
    except Exception:
        return 30.0


def _gerar_keyframes(timeline, orig_w, orig_h, crop_w, regras):
    """
    Converte a timeline de tracking em keyframes de crop (x, zoom).
    Reduz para apenas os momentos de mudanca significativa.
    """
    if not timeline:
        # Fallback: centro
        return [(0.0, (orig_w - crop_w) // 2, 1.0)]

    zoom_base = regras.get("zoom_base", 1.0)
    transition_speed = regras.get("transition_speed", 0.5)
    seguir = regras.get("seguir_speaker", True)
    zoom_prog = regras.get("zoom_progressivo", None)
    duracao_total = timeline[-1]["tempo"] if timeline else 60.0

    cam_x_atual = orig_w / 2
    ema_alpha = transition_speed
    keyframes_brutos = []

    for entry in timeline:
        t = entry["tempo"]
        tracks = entry["tracks"]
        active = entry["active_speaker"]

        target_x = cam_x_atual
        target_zoom = zoom_base

        if seguir and active is not None and active in tracks:
            x1, y1, x2, y2 = tracks[active]
            target_x = (x1 + x2) / 2
        elif tracks:
            areas = {tid: (bx[2]-bx[0])*(bx[3]-bx[1]) for tid, bx in tracks.items()}
            best = max(areas, key=areas.get)
            x1, y1, x2, y2 = tracks[best]
            target_x = (x1 + x2) / 2

        if zoom_prog:
            progresso = min(t / max(duracao_total, 1), 1.0)
            target_zoom = zoom_prog[0] + (zoom_prog[1] - zoom_prog[0]) * progresso

        cam_x_atual += (target_x - cam_x_atual) * ema_alpha

        eff_crop_w = int(crop_w / target_zoom)
        x = int(cam_x_atual - eff_crop_w / 2)
        x = max(0, min(x, orig_w - eff_crop_w))

        keyframes_brutos.append((t, x, target_zoom, eff_crop_w))

    if not keyframes_brutos:
        return [(0.0, (orig_w - crop_w) // 2, zoom_base)]

    keyframes = _reduzir_keyframes(keyframes_brutos)
    return keyframes


def _reduzir_keyframes(kf_brutos, threshold_x=70, threshold_zoom=0.05, min_gap=1.2):
    """
    Reduz keyframes mantendo apenas onde ha mudanca significativa.
    Sempre inclui o primeiro e o ultimo.
    threshold_x: mudanca minima em pixels para gerar novo keyframe
    min_gap: tempo minimo (segundos) entre keyframes consecutivos
    """
    if len(kf_brutos) <= 2:
        return [(t, x, z) for t, x, z, _ in kf_brutos]

    reduzidos = [(kf_brutos[0][0], kf_brutos[0][1], kf_brutos[0][2])]
    last_t = kf_brutos[0][0]
    last_x = kf_brutos[0][1]
    last_zoom = kf_brutos[0][2]
    last_significant_x = last_x
    last_significant_zoom = last_zoom

    for i in range(1, len(kf_brutos) - 1):
        t, x, zoom, _ = kf_brutos[i]
        dx = abs(x - last_significant_x)
        dz = abs(zoom - last_significant_zoom)
        dt = t - last_t

        if (dx > threshold_x or dz > threshold_zoom) and dt >= min_gap:
            reduzidos.append((t, x, zoom))
            last_t = t
            last_significant_x = x
            last_significant_zoom = zoom

    if len(reduzidos) > 25:
        step = len(kf_brutos) // 25
        reduzidos = [(kf_brutos[i][0], kf_brutos[i][1], kf_brutos[i][2])
                      for i in range(0, len(kf_brutos), step)]
        if kf_brutos[-1][0] != reduzidos[-1][0]:
            reduzidos.append((kf_brutos[-1][0], kf_brutos[-1][1], kf_brutos[-1][2]))

    final = kf_brutos[-1]
    reduzidos.append((final[0], final[1], final[2]))

    seen = set()
    deduped = []
    for t, x, z in reduzidos:
        key = round(t, 1)
        if key not in seen:
            seen.add(key)
            deduped.append((t, x, z))

    return deduped


def _construir_filtro_crop(keyframes, crop_w, crop_h, target_w, target_h):
    """
    Constroi a string do filtro FFmpeg com crop dinamico interpolado.

    Usa crop=w:h:x='expr':y=0 onde x é uma funcao piecewise-linear do tempo.
    """
    if not keyframes:
        return f"crop={crop_w}:{crop_h}:0:0"

    if len(keyframes) == 1:
        t, x, zoom = keyframes[0]
        eff_w = int(crop_w / zoom)
        eff_w = min(eff_w, crop_w)
        return f"crop={eff_w}:{crop_h}:{x}:0"

    parts = []
    n = len(keyframes)

    for i in range(n - 1):
        t0, x0, z0 = keyframes[i]
        t1, x1, z1 = keyframes[i + 1]
        dt = t1 - t0
        if dt < 0.01:
            dt = 0.01

        ew0 = int(crop_w / z0)
        ew1 = int(crop_w / z1)

        if i == 0:
            parts.append(f"if(lt(t,{t1:.2f}),")
            parts.append(f"{x0}+({x1}-{x0})*min(1,(t-{t0:.2f})/{dt:.2f}),")
        else:
            parts.append(f"if(lt(t,{t1:.2f}),")
            parts.append(f"{x0}+({x1}-{x0})*min(1,(t-{t0:.2f})/{dt:.2f}),")

    final_t, final_x, final_z = keyframes[-1]
    parts.append(f"{final_x}")
    parts.append(")" * (n - 1))

    x_expr = "".join(parts)

    return f"crop={crop_w}:{crop_h}:x='{x_expr}':y=0"


def _aplicar_diarizacao(timeline, diarizacao, verbose=False):
    """
    Usa a diarizacao de audio para refinar quem e o speaker ativo em cada momento.
    Mapeia speakers do audio para IDs visuais do tracking e sobrescreve o active_speaker.
    """
    if not diarizacao or not timeline:
        return timeline

    from modules.speaker_diarizer import mapear_speakers_visuais
    mapeamento, coincidencias = mapear_speakers_visuais(diarizacao, timeline)

    if not mapeamento:
        if verbose:
            print(f"  [SMART-FRAME] Diarizacao: sem mapeamento viavel")
        return timeline

    if verbose:
        print(f"  [SMART-FRAME] Mapeamento audio->visual: {mapeamento}")

    def _speaker_no_tempo(t):
        for seg in diarizacao:
            if seg["start"] <= t <= seg["end"]:
                return seg["speaker"]
        return None

    for entry in timeline:
        t = entry["tempo"]
        audio_sp = _speaker_no_tempo(t)
        if audio_sp and audio_sp in mapeamento:
            visual_tid = mapeamento[audio_sp]
            if visual_tid in entry["tracks"]:
                entry["active_speaker"] = visual_tid
                entry["audio_guided"] = True

    return timeline


def _detectar_reacoes(timeline, regras, verbose=False):
    """
    Detecta reacoes (riso, surpresa) via pico de movimento facial em nao-speakers.
    Para categorias com cortar_reacao=True, desvia camera para o reator.

    Logica:
    - Identifica o speaker baseline (mais frequente)
    - Detecta nao-speakers com motion spike (muito acima do speaker)
    - Após reaction_delay, corta para o reator por reaction_hold segundos
    """
    if not regras.get("cortar_reacao") or len(timeline) < 8:
        return timeline, 0

    delay = regras.get("reaction_delay", 0.4)
    hold = regras.get("reaction_hold", 2.0)
    sample_dt = timeline[1]["tempo"] - timeline[0]["tempo"] if len(timeline) > 1 else 0.25

    from collections import Counter
    speaker_counts = Counter(
        e["active_speaker"] for e in timeline
        if e["active_speaker"] is not None
    )
    if not speaker_counts:
        return timeline, 0
    main_speaker = speaker_counts.most_common(1)[0][0]

    spike_windows = []
    current_reactor = None
    current_start = None
    current_end = None

    for entry in timeline:
        active = entry["active_speaker"]
        scores = entry["motion_scores"]
        t = entry["tempo"]

        speaker_score = scores.get(main_speaker, 0)

        best_reactor = None
        best_reactor_score = 0
        for tid, score in scores.items():
            if tid != main_speaker and score > best_reactor_score:
                best_reactor = tid
                best_reactor_score = score

        if best_reactor is None:
            if current_reactor is not None and t - current_end > 0.5:
                spike_windows.append((current_start, current_end, current_reactor))
                current_reactor = None
            continue

        is_spike = (
            best_reactor_score > MIN_MOTION_THRESHOLD * 1.2
            and best_reactor_score > speaker_score * 1.4
        )

        if is_spike:
            if current_reactor == best_reactor:
                current_end = t
            else:
                if current_reactor is not None:
                    spike_windows.append((current_start, current_end, current_reactor))
                current_reactor = best_reactor
                current_start = t
                current_end = t
        else:
            if current_reactor is not None and t - current_end > 0.5:
                spike_windows.append((current_start, current_end, current_reactor))
                current_reactor = None

    if current_reactor is not None:
        spike_windows.append((current_start, current_end, current_reactor))

    reaction_count = 0
    for raw_start, raw_end, reactor_tid in spike_windows:
        raw_dur = raw_end - raw_start
        if raw_dur < 0.5:
            continue

        cut_start = raw_start + delay
        actual_hold = min(hold, raw_dur + 0.8)
        cut_end = min(cut_start + actual_hold, raw_end + delay + 0.3)

        for entry in timeline:
            t = entry["tempo"]
            if cut_start <= t <= cut_end:
                if reactor_tid in entry["tracks"]:
                    entry["active_speaker"] = reactor_tid
                    entry["reaction"] = True

        reaction_count += 1

    if verbose and reaction_count:
        print(f"  [SMART-FRAME] Reacoes: {reaction_count} cortes para reator")

    return timeline, reaction_count


def gerar_smart_crop_filter(caminho_video, inicio_seg, fim_seg,
                             orig_w, orig_h, crop_w, target_w=1080,
                             target_h=1920, categoria=None, verbose=True,
                             usar_diarizacao=True):
    """
    Funcao principal. Gera um filtro FFmpeg de crop dinamico inteligente.

    Retorna: string do filtro (ex: "crop=608:1080:x='...':0")
             ou None se falhar (caller faz fallback para crop centralizado).
    """
    if not HAS_CV2 or not HAS_YOLO:
        if verbose:
            print("  [SMART-FRAME] OpenCV/YOLO nao disponivel, fallback")
        return None

    regras = _obter_regras(categoria)
    if verbose:
        print(f"  [SMART-FRAME] Categoria: {categoria or 'default'} | "
              f"zoom_base: {regras.get('zoom_base', 1.0)}")

    diarizacao = None
    timeline = None

    if usar_diarizacao:
        try:
            from modules.speaker_diarizer import diarizar as _diar_fn
        except ImportError:
            _diar_fn = None
    else:
        _diar_fn = None

    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_diar = pool.submit(_diar_fn, caminho_video, inicio_seg, fim_seg) if _diar_fn else None
        fut_track = pool.submit(_rastrear_segmento, caminho_video, inicio_seg, fim_seg)

        diarizacao = fut_diar.result() if fut_diar else None
        timeline = fut_track.result()

    if diarizacao and verbose:
        print(f"  [SMART-FRAME] Diarizacao: {len(diarizacao)} segments ativos")

    if not timeline:
        if verbose:
            print("  [SMART-FRAME] Nenhuma deteccao, fallback centro")
        return None

    if diarizacao:
        timeline = _aplicar_diarizacao(timeline, diarizacao, verbose=verbose)

    timeline, n_reacoes = _detectar_reacoes(timeline, regras, verbose=verbose)

    n_speakers = len(set(
        e["active_speaker"] for e in timeline if e["active_speaker"] is not None
    ))
    if verbose:
        audio_tag = " + audio" if diarizacao else ""
        react_tag = f" | {n_reacoes} reacoes" if n_reacoes else ""
        print(f"  [SMART-FRAME] {len(timeline)} amostras | "
              f"{n_speakers} speakers{audio_tag}{react_tag}")

    keyframes = _gerar_keyframes(timeline, orig_w, orig_h, crop_w, regras)

    if verbose:
        print(f"  [SMART-FRAME] {len(keyframes)} keyframes gerados")
        if len(keyframes) <= 8:
            for t, x, z in keyframes:
                print(f"    t={t:.1f}s x={x} zoom={z:.2f}")

    filtro = _construir_filtro_crop(keyframes, crop_w, orig_h, target_w, target_h)
    return filtro


def diagnosticar_smart_crop(caminho_video, inicio_seg, fim_seg, categoria=None,
                             output_path=None):
    """
    Modo diagnostico: gera um video side-by-side mostrando o tracking
    e o resultado do auto-framing. util para debug e demo.
    """
    if not HAS_CV2 or not HAS_YOLO:
        print("[SMART-FRAME] Dependencias nao disponiveis")
        return None

    model = _carregar_modelo()
    regras = _obter_regras(categoria)

    cap = cv2.VideoCapture(caminho_video)
    if not cap.isOpened():
        return None

    fps = int(cap.get(cv2.CAP_PROP_FPS)) or 30
    orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    crop_w = min(int(orig_h * 9 / 16), orig_w)

    cap.set(cv2.CAP_PROP_POS_FRAMES, int(inicio_seg * fps))
    total_clip = int((fim_seg - inicio_seg) * fps)

    detector = SpeakerDetector()
    rosto_cache = {}
    cam_x = orig_w / 2.0
    ema_alpha = regras.get("transition_speed", 0.5)
    zoom_base = regras.get("zoom_base", 1.0)

    panel_h = 720
    left_w = int(orig_w * panel_h / orig_h)
    right_w = int(crop_w * panel_h / orig_h)
    gap = 20
    out_w = left_w + gap + right_w

    if output_path is None:
        output_path = os.path.join("output", "smart_frame_diag.mp4")

    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo", "-vcodec", "rawvideo", "-pix_fmt", "bgr24",
        "-s", f"{out_w}x{panel_h}", "-r", str(min(fps, 30)), "-i", "-",
        "-c:v", "h264_nvenc", "-preset", "p4", "-cq", "21",
        "-pix_fmt", "yuv420p", output_path,
    ]
    proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)

    frame_idx = 0
    sample_rate = max(1, fps // 30)

    PALETA = [
        (0, 255, 128), (255, 100, 0), (0, 165, 255), (255, 0, 255),
        (0, 255, 255), (255, 255, 0), (128, 0, 255), (0, 128, 255),
    ]

    try:
        while frame_idx < total_clip:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % sample_rate != 0:
                frame_idx += 1
                continue

            tempo = frame_idx / fps
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            results = model.track(
                frame, classes=[0], tracker="bytetrack.yaml",
                verbose=False, conf=0.35, persist=True,
                device=0, imgsz=640,
            )

            tracks = {}
            if results and results[0].boxes is not None and len(results[0].boxes) > 0:
                for box in results[0].boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    tid = int(box.id[0]) if box.id is not None else 0
                    tracks[tid] = (x1, y1, x2, y2)

            rostos = _detectar_rostos(gray, tracks, cache=rosto_cache)
            active_tid, score, all_scores = detector.atualizar(tracks, gray, tempo, rostos=rostos)

            cena = frame.copy()
            for tid, (x1, y1, x2, y2) in tracks.items():
                is_speaker = (tid == active_tid)
                is_occluded = tid in detector.occluded
                if is_speaker:
                    cor = (0, 255, 0)
                elif is_occluded:
                    cor = (128, 128, 128)
                else:
                    cor = PALETA[tid % len(PALETA)]

                cv2.rectangle(cena, (x1, y1), (x2, y2), cor, 3 if is_speaker else 2)
                ms = all_scores.get(tid, 0)
                tags = ""
                if is_speaker:
                    tags = " SPEAKING"
                if is_occluded:
                    tags += " OCCL"
                label = f"#{tid}{tags} m={ms:.1f}"
                font = cv2.FONT_HERSHEY_SIMPLEX
                (tw, th), bl = cv2.getTextSize(label, font, 0.5, 1)
                ytop = max(0, y1 - th - bl - 4)
                cv2.rectangle(cena, (x1, ytop), (x1 + tw + 6, ytop + th + bl + 2), cor, -1)
                cv2.putText(cena, label, (x1 + 3, ytop + th + 1), font, 0.5, (0, 0, 0), 1, cv2.LINE_AA)

            if active_tid and active_tid in tracks:
                x1, y1, x2, y2 = tracks[active_tid]
                cam_x += ((x1 + x2) / 2 - cam_x) * ema_alpha

            eff_w = int(crop_w / zoom_base)
            crop_x = max(0, min(int(cam_x - eff_w / 2), orig_w - crop_w))
            cv2.rectangle(cena, (crop_x, 0), (crop_x + crop_w, orig_h), (0, 255, 255), 3)

            crop_frame = frame[:, crop_x:crop_x + crop_w]

            cena_small = cv2.resize(cena, (left_w, panel_h))
            frame_small = cv2.resize(crop_frame, (right_w, panel_h))

            composicao = np.zeros((panel_h, out_w, 3), dtype=np.uint8)
            composicao[:, :left_w] = cena_small
            composicao[:, left_w + gap:] = frame_small

            info_lines = [
                f"t={tempo:.1f}s | cat={categoria or 'default'}",
                f"Pessoas: {len(tracks)} | Speaker: #{active_tid if active_tid else '-'}",
                f"Camera X: {cam_x:.0f} | Zoom: {zoom_base:.1f}x",
            ]
            for i, line in enumerate(info_lines):
                cv2.putText(composicao, line, (10, 25 + i * 25),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2, cv2.LINE_AA)

            proc.stdin.write(composicao.tobytes())
            frame_idx += 1
    finally:
        cap.release()
        proc.stdin.close()
        proc.wait()

    print(f"[SMART-FRAME] Diagnostico salvo: {output_path}")
    return output_path
