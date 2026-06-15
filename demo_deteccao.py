#!/usr/bin/env python3
"""
Demo de Deteccao Visual — mostra como o sistema "ve" pessoas e rostos no video.
Desenha bounding boxes com tracking de IDs (Person #1, #2, ...) e deteccao de rostos.

Uso:
    python demo_deteccao.py <video_entrada> [video_saida]
"""

import sys
import time
import os
import subprocess

import cv2
import numpy as np
from ultralytics import YOLO


VIDEO_ENTRADA = "output/corte_Teste_limpo.mp4"
VIDEO_SAIDA = "output/demo_deteccao.mp4"
YOLO_MODEL = "yolov8n.pt"

COR_INFO_BG = (0, 0, 0)
COR_INFO_TXTO = (255, 255, 255)

PALETA_PESSOAS = [
    (0, 255, 128),
    (255, 100, 0),
    (0, 165, 255),
    (255, 0, 255),
    (0, 255, 255),
    (255, 255, 0),
    (128, 0, 255),
    (0, 128, 255),
    (50, 200, 50),
    (200, 50, 200),
]


def cor_por_id(track_id):
    return PALETA_PESSOAS[int(track_id) % len(PALETA_PESSOAS)]


def desenhar_label(img, texto, x1, y1, cor):
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.6
    thickness = 2
    (tw, th), baseline = cv2.getTextSize(texto, font, scale, thickness)
    y_top = max(0, y1 - th - baseline - 6)
    cv2.rectangle(img, (x1, y_top), (x1 + tw + 8, y_top + th + baseline + 4), cor, -1)
    cv2.putText(img, texto, (x1 + 4, y_top + th + 2), font, scale, (0, 0, 0), thickness, cv2.LINE_AA)


def desenhar_painel_info(img, fps, n_pessoas, n_rostos, frame_idx, total_frames):
    h, w = img.shape[:2]
    linhas = [
        f"FPS: {fps:.1f}",
        f"Frame: {frame_idx}/{total_frames}",
        f"Pessoas detectadas: {n_pessoas}",
        f"Rostos detectados: {n_rostos}",
    ]
    pad = 12
    lh = 28
    panel_w = 340
    panel_h = lh * len(linhas) + pad * 2
    overlay = img.copy()
    cv2.rectangle(overlay, (0, 0), (panel_w, panel_h), COR_INFO_BG, -1)
    cv2.addWeighted(overlay, 0.65, img, 0.35, 0, img)
    cv2.rectangle(img, (0, 0), (panel_w, panel_h), (100, 100, 100), 1)
    for i, linha in enumerate(linhas):
        y = pad + lh * i + lh // 2 + 4
        cv2.putText(img, linha, (pad, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, COR_INFO_TXTO, 2, cv2.LINE_AA)


def iniciar_ffmpeg(saida, w, h, fps_out):
    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
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
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
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

    print(f"[DEMO] Carregando modelo YOLO ({YOLO_MODEL})...", flush=True)
    model = YOLO(YOLO_MODEL)

    cascade_path = os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
    face_cascade = cv2.CascadeClassifier(cascade_path)

    cap = cv2.VideoCapture(entrada)
    if not cap.isOpened():
        print(f"[ERRO] Nao foi possivel abrir: {entrada}")
        sys.exit(1)

    fps_orig = int(cap.get(cv2.CAP_PROP_FPS))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps_out = 30
    processar_a_cada = max(1, fps_orig // fps_out)

    print(f"[DEMO] Video: {w}x{h} @ {fps_orig}fps | {total} frames", flush=True)
    print(f"[DEMO] Saida: {saida} @ {fps_out}fps (processa 1 a cada {processar_a_cada})", flush=True)
    print(f"[DEMO] Iniciando encoder FFmpeg...", flush=True)

    proc = iniciar_ffmpeg(saida, w, h, fps_out)

    print(f"[DEMO] Processando... (GPU ativa)", flush=True)

    frame_idx = 0
    escritos = 0
    t_inicio = time.time()

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % processar_a_cada != 0:
                frame_idx += 1
                continue

            results = model.track(
                frame,
                classes=[0],
                tracker="bytetrack.yaml",
                verbose=False,
                conf=0.4,
                persist=True,
                device=0,
                imgsz=480,
            )

            n_pessoas = 0
            if results and results[0].boxes is not None and len(results[0].boxes) > 0:
                boxes = results[0].boxes
                for box in boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0])
                    conf = float(box.conf[0]) if box.conf is not None else 0.0
                    track_id = int(box.id[0]) if box.id is not None else n_pessoas + 1
                    cor = cor_por_id(track_id)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), cor, 3)
                    cv2.rectangle(frame, (x1, y1), (x1 + 6, y2), cor, -1)
                    cv2.rectangle(frame, (x2 - 6, y1), (x2, y2), cor, -1)
                    label = f"Person #{track_id}  {conf*100:.0f}%"
                    desenhar_label(frame, label, x1, y1, cor)
                    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                    cv2.circle(frame, (cx, cy), 5, cor, -1)
                    cv2.line(frame, (x1, cy), (x2, cy), cor, 1)
                    cv2.line(frame, (cx, y1), (cx, y2), cor, 1)
                    n_pessoas += 1

            small = cv2.resize(frame, (w // 2, h // 2))
            gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            rostos = face_cascade.detectMultiScale(gray, scaleFactor=1.15, minNeighbors=5, minSize=(30, 30))
            n_rostos = len(rostos)
            for (fx, fy, fw, fh) in rostos:
                fx, fy, fw, fh = fx * 2, fy * 2, fw * 2, fh * 2
                cv2.rectangle(frame, (fx, fy), (fx + fw, fy + fh), (0, 200, 255), 2)
                cv2.circle(frame, (fx + fw // 2, fy + fh // 2), 3, (0, 200, 255), -1)

            fps_atual = (escritos + 1) / max(time.time() - t_inicio, 0.001)
            desenhar_painel_info(frame, fps_atual, n_pessoas, n_rostos, frame_idx + 1, total)

            proc.stdin.write(frame.tobytes())
            escritos += 1
            frame_idx += 1

            if escritos % 30 == 0:
                print(f"  ...{escritos} frames escritos ({frame_idx}/{total}) | FPS: {fps_atual:.1f} | pessoas: {n_pessoas} | rostos: {n_rostos}", flush=True)
    finally:
        cap.release()
        proc.stdin.close()
        proc.wait()

    tempo_total = time.time() - t_inicio
    print(f"\n[DEMO] Concluido em {tempo_total:.1f}s", flush=True)
    print(f"[DEMO] Video salvo em: {saida}", flush=True)
    print(f"[DEMO] Frames processados: {escritos}", flush=True)


if __name__ == "__main__":
    main()
