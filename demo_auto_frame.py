#!/usr/bin/env python3
"""
Prototipo: Auto-Framing Inteligente para Podcast.
Detecta quem esta falando via movimento facial e controla a camera 9:16
para seguir o speaker ativo.

Saida: video side-by-side mostrando a cena completa com deteccoes
ao lado do resultado auto-framed.

Uso:
    python demo_auto_frame.py <video_entrada> [video_saida]
"""

import sys
import time
import os
import subprocess
import collections

import cv2
import numpy as np
from ultralytics import YOLO


VIDEO_ENTRADA = "temp/segmento_demo.mp4"
VIDEO_SAIDA = "output/demo_auto_frame.mp4"
YOLO_MODEL = "yolov8n.pt"

CROP_W_9x16 = 608
SPEAKER_SWITCH_COOLDOWN = 1.5
EMA_ALPHA = 0.08
MOTION_HISTORY = 5

PALETA = [
    (0, 255, 128),
    (255, 100, 0),
    (0, 165, 255),
    (255, 0, 255),
    (0, 255, 255),
    (255, 255, 0),
    (128, 0, 255),
    (0, 128, 255),
]


def cor_por_id(tid):
    return PALETA[int(tid) % len(PALETA)]


class SpeakerDetector:
    def __init__(self):
        self.face_anterior = {}
        self.motion_scores = {}
        self.motion_history = {}
        self.active_speaker = None
        self.active_since = 0
        self.tempo_atual = 0

    def atualizar(self, tracks, frame_gray, tempo):
        self.tempo_atual = tempo
        frame_motion = {}

        for tid, (x1, y1, x2, y2) in tracks.items():
            fx1 = max(0, x1)
            fy1 = max(0, y1)
            fx2 = min(frame_gray.shape[1], x2)
            face_h = int((y2 - y1) * 0.35)
            fy2 = min(frame_gray.shape[0], y1 + face_h)

            if fx2 <= fx1 or fy2 <= fy1:
                continue

            face_roi = frame_gray[fy1:fy2, fx1:fx2]
            face_roi = cv2.resize(face_roi, (64, 32))
            face_roi = cv2.equalizeHist(face_roi)

            if tid in self.face_anterior:
                diff = cv2.absdiff(face_roi, self.face_anterior[tid])
                motion = float(np.mean(diff))
            else:
                motion = 0.0

            self.face_anterior[tid] = face_roi.copy()
            frame_motion[tid] = motion

            if tid not in self.motion_history:
                self.motion_history[tid] = collections.deque(maxlen=MOTION_HISTORY)
            self.motion_history[tid].append(motion)

            avg_motion = np.mean(self.motion_history[tid])
            self.motion_scores[tid] = avg_motion

        for tid in list(self.motion_scores.keys()):
            if tid not in tracks:
                del self.motion_scores[tid]
                self.face_anterior.pop(tid, None)
                self.motion_history.pop(tid, None)

        if not self.motion_scores:
            return self.active_speaker, 0.0

        best_tid = max(self.motion_scores, key=self.motion_scores.get)
        best_score = self.motion_scores[best_tid]

        if best_score < 1.5:
            return self.active_speaker, best_score

        if self.active_speaker is None:
            self.active_speaker = best_tid
            self.active_since = tempo
        elif best_tid != self.active_speaker:
            if tempo - self.active_since >= SPEAKER_SWITCH_COOLDOWN:
                margin = best_score - self.motion_scores.get(self.active_speaker, 0)
                if margin > 0.5:
                    self.active_speaker = best_tid
                    self.active_since = tempo

        return self.active_speaker, best_score


class CameraController:
    def __init__(self, orig_w, orig_h, crop_w):
        self.orig_w = orig_w
        self.orig_h = orig_h
        self.crop_w = crop_w
        self.cam_x = orig_w / 2
        self.target_x = orig_w / 2

    def seguir(self, target_x):
        self.target_x = target_x
        self.cam_x += (self.target_x - self.cam_x) * EMA_ALPHA

    def get_crop(self):
        x = int(self.cam_x - self.crop_w / 2)
        x = max(0, min(x, self.orig_w - self.crop_w))
        return x, 0, self.crop_w, self.orig_h

    def get_viewport_rect(self):
        x = int(self.cam_x - self.crop_w / 2)
        x = max(0, min(x, self.orig_w - self.crop_w))
        return x, 0, x + self.crop_w, self.orig_h


def desenhar_label(img, texto, x1, y1, cor, scale=0.5, thickness=1):
    font = cv2.FONT_HERSHEY_SIMPLEX
    (tw, th), baseline = cv2.getTextSize(texto, font, scale, thickness)
    y_top = max(0, y1 - th - baseline - 4)
    cv2.rectangle(img, (x1, y_top), (x1 + tw + 6, y_top + th + baseline + 2), cor, -1)
    cv2.putText(img, texto, (x1 + 3, y_top + th + 1), font, scale, (0, 0, 0), thickness, cv2.LINE_AA)


def montar_side_by_side(cena_full, crop_x, crop_y, crop_w, crop_h, info_text):
    h_full = 720
    w_full = int(cena_full.shape[1] * h_full / cena_full.shape[0])
    cena_small = cv2.resize(cena_full, (w_full, h_full))

    scale_factor = w_full / cena_full.shape[1]
    sx = int(crop_x * scale_factor)
    sw = int(crop_w * scale_factor)
    cv2.rectangle(cena_small, (sx, 0), (sx + sw, h_full), (0, 255, 255), 3)

    frame_crop = cena_full[crop_y:crop_y + crop_h, crop_x:crop_x + crop_w]
    h_frame = 720
    w_frame = int(frame_crop.shape[1] * h_frame / frame_crop.shape[0])
    frame_resized = cv2.resize(frame_crop, (w_frame, h_frame))

    gap = 20
    total_w = w_full + gap + w_frame
    result = np.zeros((h_full, total_w, 3), dtype=np.uint8)
    result[:, :w_full] = cena_small
    result[:, w_full + gap:] = frame_resized

    cv2.rectangle(result, (w_full, 0), (w_full + gap - 1, h_full), (40, 40, 40), -1)

    font = cv2.FONT_HERSHEY_SIMPLEX
    for i, linha in enumerate(info_text):
        cv2.putText(result, linha, (10, 25 + i * 25), font, 0.55, (255, 255, 255), 2, cv2.LINE_AA)

    label_x = w_full + gap + 10
    cv2.rectangle(result, (label_x, 0), (label_x + 160, 30), (0, 100, 0), -1)
    cv2.putText(result, "AUTO-FRAMED 9:16", (label_x + 5, 20), font, 0.5, (255, 255, 255), 1, cv2.LINE_AA)

    cv2.rectangle(result, (10, 0), (120, 30), (0, 0, 80), -1)
    cv2.putText(result, "DETECCOES", (15, 20), font, 0.5, (255, 255, 255), 1, cv2.LINE_AA)

    return result


def iniciar_ffmpeg(saida, w, h, fps_out):
    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo", "-vcodec", "rawvideo",
        "-pix_fmt", "bgr24",
        "-s", f"{w}x{h}",
        "-r", str(fps_out),
        "-i", "-",
        "-c:v", "h264_nvenc",
        "-preset", "p4",
        "-cq", "21",
        "-pix_fmt", "yuv420p",
        saida,
    ]
    try:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        return proc
    except Exception:
        cmd_alt = [
            "ffmpeg", "-y",
            "-f", "rawvideo", "-vcodec", "rawvideo",
            "-pix_fmt", "bgr24",
            "-s", f"{w}x{h}",
            "-r", str(fps_out),
            "-i", "-",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "20",
            "-pix_fmt", "yuv420p",
            saida,
        ]
        return subprocess.Popen(cmd_alt, stdin=subprocess.PIPE, stderr=subprocess.PIPE)


def main():
    entrada = sys.argv[1] if len(sys.argv) > 1 else VIDEO_ENTRADA
    saida = sys.argv[2] if len(sys.argv) > 2 else VIDEO_SAIDA

    if not os.path.exists(entrada):
        print(f"[ERRO] Video nao encontrado: {entrada}")
        sys.exit(1)

    print(f"[AUTO-FRAME] Carregando YOLO ({YOLO_MODEL})...", flush=True)
    model = YOLO(YOLO_MODEL)

    cap = cv2.VideoCapture(entrada)
    if not cap.isOpened():
        print(f"[ERRO] Nao foi possivel abrir: {entrada}")
        sys.exit(1)

    fps = int(cap.get(cv2.CAP_PROP_FPS)) or 30
    orig_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    orig_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    crop_w = min(CROP_W_9x16, orig_w)
    camera = CameraController(orig_w, orig_h, crop_w)
    speaker_det = SpeakerDetector()

    print(f"[AUTO-FRAME] Video: {orig_w}x{orig_h} @ {fps}fps | {total} frames", flush=True)
    print(f"[AUTO-FRAME] Crop 9:16: {crop_w}x{orig_h}", flush=True)
    print(f"[AUTO-FRAME] Processando...", flush=True)

    panel_h = 720
    panel_left_w = int(orig_w * panel_h / orig_h)
    panel_right_w = int(crop_w * panel_h / orig_h)
    gap = 20
    out_w = panel_left_w + gap + panel_right_w
    out_h = panel_h

    proc = iniciar_ffmpeg(saida, out_w, out_h, fps)

    frame_idx = 0
    t_inicio = time.time()
    processar_a_cada = 1

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % processar_a_cada != 0:
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
                    conf = float(box.conf[0])
                    tracks[tid] = (x1, y1, x2, y2)

            active_tid, motion_score = speaker_det.atualizar(tracks, gray, tempo)

            cena = frame.copy()
            for tid, (x1, y1, x2, y2) in tracks.items():
                is_speaker = (tid == active_tid)
                cor = (0, 255, 0) if is_speaker else cor_por_id(tid)
                thickness = 4 if is_speaker else 2
                cv2.rectangle(cena, (x1, y1), (x2, y2), cor, thickness)

                face_h = int((y2 - y1) * 0.35)
                cv2.rectangle(cena, (x1, y1), (x2, y1 + face_h), cor, 1)

                ms = speaker_det.motion_scores.get(tid, 0)
                label = f"#{tid} {'SPEAKING' if is_speaker else ''} m={ms:.1f}"
                desenhar_label(cena, label, x1, y1, cor, scale=0.5, thickness=1)

                if is_speaker:
                    cv2.circle(cena, ((x1 + x2) // 2, (y1 + y1 + face_h) // 2), 8, (0, 255, 0), 2)
                    cv2.line(cena, ((x1 + x2) // 2 - 15, (y1 + y1 + face_h) // 2),
                             ((x1 + x2) // 2 + 15, (y1 + y1 + face_h) // 2), (0, 255, 0), 2)
                    cv2.line(cena, ((x1 + x2) // 2, (y1 + y1 + face_h) // 2 - 15),
                             ((x1 + x2) // 2, (y1 + y1 + face_h) // 2 + 15), (0, 255, 0), 2)

            if active_tid is not None and active_tid in tracks:
                x1, y1, x2, y2 = tracks[active_tid]
                face_center_x = (x1 + x2) // 2
                camera.seguir(face_center_x)

            crop_x, crop_y, cw, ch = camera.get_crop()
            vx1, vy1, vx2, vy2 = camera.get_viewport_rect()
            cv2.rectangle(cena, (vx1, vy1), (vx2, vy2), (0, 255, 255), 2)
            for i in range(0, ch, 40):
                cv2.line(cena, (vx1, vy1 + i), (vx1 + 8, vy1 + i), (0, 255, 255), 1)
                cv2.line(cena, (vx2 - 8, vy1 + i), (vx2, vy1 + i), (0, 255, 255), 1)

            fps_atual = (frame_idx + 1) / max(time.time() - t_inicio, 0.001)
            info = [
                f"FPS: {fps_atual:.1f}",
                f"Frame: {frame_idx}/{total}",
                f"Pessoas: {len(tracks)}",
                f"Speaker ativo: #{active_tid}" + (f" (m={motion_score:.1f})" if active_tid else " ---"),
                f"Camera X: {camera.cam_x:.0f}",
            ]
            composicao = montar_side_by_side(cena, crop_x, crop_y, cw, ch, info)
            proc.stdin.write(composicao.tobytes())

            frame_idx += 1
            if frame_idx % (fps * 2) == 0:
                print(f"  ...{frame_idx}/{total} | FPS: {fps_atual:.1f} | pessoas: {len(tracks)} | "
                      f"speaker: #{active_tid} | cam_x: {camera.cam_x:.0f}", flush=True)
    finally:
        cap.release()
        proc.stdin.close()
        proc.wait()

    tempo_total = time.time() - t_inicio
    print(f"\n[AUTO-FRAME] Concluido em {tempo_total:.1f}s", flush=True)
    print(f"[AUTO-FRAME] Video salvo em: {saida}", flush=True)


if __name__ == "__main__":
    main()
