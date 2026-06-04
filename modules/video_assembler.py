import os
import numpy as np
from moviepy import (
    ImageClip,
    AudioFileClip,
    concatenate_videoclips,
    concatenate_audioclips,
)
from PIL import Image
from config import RESOLUCAO, DURACAO_IMAGEM, PASTA_TEMP, PASTA_OUTPUT


def montar_video(caminhos_imagens, caminhos_audios, titulo="video"):
    clips_audio = []
    for c in caminhos_audios:
        clip_a = AudioFileClip(c)
        clips_audio.append(clip_a)

    duracao_total = sum(a.duration for a in clips_audio)

    if not caminhos_imagens:
        caminhos_imagens = [f"{PASTA_TEMP}/img_placeholder_0.jpg"]

    duracao_por_imagem = duracao_total / len(caminhos_imagens)

    clips_video = []
    for i, img_path in enumerate(caminhos_imagens):
        img = Image.open(img_path)
        img = img.resize(RESOLUCAO, Image.LANCZOS)

        frames_dir = f"{PASTA_TEMP}/frames_{i}"
        os.makedirs(frames_dir, exist_ok=True)

        fps = 24
        n_frames = int(duracao_por_imagem * fps)
        zoom_inicio = 1.0
        zoom_fim = 1.30

        for f_idx in range(n_frames):
            progresso = f_idx / max(n_frames - 1, 1)
            zoom = zoom_inicio + (zoom_fim - zoom_inicio) * progresso
            w, h = img.size
            novo_w = int(w * zoom)
            novo_h = int(h * zoom)
            frame_img = img.resize((novo_w, novo_h), Image.LANCZOS)
            y_off = (novo_h - h) // 2
            x_off = (novo_w - w) // 2
            frame_img = frame_img.crop((x_off, y_off, x_off + w, y_off + h))
            frame_img.save(f"{frames_dir}/frame_{f_idx:05d}.jpg", quality=90)

        from moviepy import ImageSequenceClip
        clip = ImageSequenceClip(frames_dir, fps=fps)
        clips_video.append(clip)
        print(f"    [{i+1}/{len(caminhos_imagens)}] clip gerado")

    video = concatenate_videoclips(clips_video)

    audios = [AudioFileClip(c) for c in caminhos_audios]
    audio_concat = concatenate_audioclips(audios)

    video = video.with_audio(audio_concat)
    video = video.with_duration(min(video.duration, audio_concat.duration))

    caminho_saida = f"{PASTA_OUTPUT}/{titulo.replace(' ', '_')}.mp4"
    print("  Encodando vídeo final...")
    video.write_videofile(
        caminho_saida,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        audio_bitrate="192k",
        preset="medium",
        threads=4,
        logger=None,
    )

    _limpar_temp()
    return caminho_saida


def _limpar_temp():
    import shutil
    for f in os.listdir(PASTA_TEMP):
        caminho = os.path.join(PASTA_TEMP, f)
        if f.startswith("resized_") or f.startswith("frames_"):
            if os.path.isdir(caminho):
                shutil.rmtree(caminho)
            else:
                os.remove(caminho)
