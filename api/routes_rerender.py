import os
import sys
import io
import re
import json
import hashlib
import threading
import subprocess
from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import StreamingResponse, JSONResponse
from typing import Optional

from api.state import PASTA_OUTPUT, PASTA_TEMP
from api.routes_process import _get_state, _get_loop, _emit
from api.ws_manager import manager as ws_manager

router = APIRouter()

_preview_cache = {}
_preview_cache_lock = threading.Lock()
_PREVIEW_CACHE_MAX = 50


def _preview_cache_key(cut_id, body):
    raw = json.dumps(body, sort_keys=True)
    return f"{cut_id}:{hashlib.md5(raw.encode()).hexdigest()}"


@router.post("/cut/{cut_id}/preview")
async def preview_subtitle(cut_id: str, body: dict):
    import asyncio
    from urllib.parse import unquote
    cut_id = unquote(cut_id)

    cache_key = _preview_cache_key(cut_id, body)
    with _preview_cache_lock:
        if cache_key in _preview_cache:
            buf = io.BytesIO(_preview_cache[cache_key])
            buf.seek(0)
            return StreamingResponse(buf, media_type="image/jpeg")

    meta = await asyncio.to_thread(_get_cut_data, cut_id)
    if not meta:
        return JSONResponse({"error": f"cut not found: {cut_id}"}, status_code=404)

    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    import modules.subtitle_generator as sub_mod

    font_size = body.get("font_size", 52)
    margin_bottom = body.get("text_margin_bottom", 180)
    estilo = body.get("subtitle_style", "karaoke")
    crop = body.get("crop_vertical", True)

    sub_mod.FONT_SIZE = font_size
    sub_mod.TEXT_MARGIN_BOTTOM = margin_bottom
    sub_mod.BASE_COLOR = body.get("base_color", "#B4B4B4")
    sub_mod.HIGHLIGHT_COLOR = body.get("highlight_color", "#FFFF32")

    img = await asyncio.to_thread(sub_mod._generate_preview_frame, cut_id, meta, estilo, crop)
    if img is None:
        return JSONResponse({"error": "failed to generate preview"}, status_code=500)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=75)
    buf.seek(0)
    img_bytes = buf.getvalue()

    with _preview_cache_lock:
        if len(_preview_cache) >= _PREVIEW_CACHE_MAX:
            oldest = next(iter(_preview_cache))
            del _preview_cache[oldest]
        _preview_cache[cache_key] = img_bytes

    buf.seek(0)
    return StreamingResponse(buf, media_type="image/jpeg")


_transc_cache = {}


def _transcrever_corte_local(cut_path):
    import os
    key = (str(cut_path), int(os.path.getmtime(cut_path)))
    if key in _transc_cache:
        return _transc_cache[key]

    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(cut_path)],
            capture_output=True, text=True, timeout=10,
        )
        duracao = float(probe.stdout.strip())
    except Exception:
        return None, 0

    try:
        from modules.parakeet_transcriber import transcrever_com_parakeet
        print(f"  [RERENDER] Transcrevendo corte renomeado ({duracao:.0f}s)...")
        result = transcrever_com_parakeet(str(cut_path))
        segmentos = result.get("segmentos", [])
        _transc_cache[key] = segmentos
        if len(_transc_cache) > 20:
            oldest = next(iter(_transc_cache))
            del _transc_cache[oldest]
        return segmentos, duracao
    except Exception as e:
        print(f"  [RERENDER] Parakeet falhou: {e}")
        return None, duracao


def _get_cut_data(cut_id):
    meta_name = cut_id.replace("corte_", "") + "_meta.json"
    meta_path = PASTA_TEMP / meta_name
    if meta_path.exists():
        with open(meta_path, "r", encoding="utf-8") as f:
            return json.load(f)

    meta_path = PASTA_TEMP / f"{cut_id}_meta.json"
    if meta_path.exists():
        with open(meta_path, "r", encoding="utf-8") as f:
            return json.load(f)

    cut_filename = cut_id if cut_id.endswith(".mp4") else f"{cut_id}.mp4"
    cut_titulo = cut_filename.replace("corte_", "").replace(".mp4", "")

    cut_path = PASTA_OUTPUT / cut_filename
    if not cut_path.exists():
        for d in PASTA_OUTPUT.iterdir():
            if d.is_dir():
                candidate = d / cut_filename
                if candidate.exists():
                    cut_path = candidate
                    break
    if not cut_path.exists():
        return None

    segmentos, duracao = _transcrever_corte_local(cut_path)
    if not segmentos:
        return None

    return {
        "video_origem": str(cut_path),
        "inicio": 0,
        "fim": duracao,
        "titulo": cut_id,
        "segmentos": segmentos,
        "fallback": False,
    }


@router.get("/cut/{cut_id}")
async def get_cut_meta(cut_id: str):
    meta = _get_cut_data(cut_id)
    if not meta:
        return JSONResponse({"error": "cut not found"}, status_code=404)
    return meta


@router.post("/cut/{cut_id}/rerender")
async def rerender_cut(cut_id: str, body: dict):
    from urllib.parse import unquote
    cut_id = unquote(cut_id)

    meta = _get_cut_data(cut_id)
    if not meta:
        return JSONResponse({"error": "cut not found"}, status_code=404)

    s = _get_state()
    if s.processing:
        return JSONResponse({"error": "already processing"}, status_code=409)

    import asyncio
    import api.routes_process as rp
    rp._main_loop = asyncio.get_running_loop()

    thread = threading.Thread(
        target=_rerender_thread,
        args=(cut_id, body, meta),
        daemon=True,
    )
    thread.start()

    return {"status": "started"}


def _rerender_thread(cut_id, render_config, meta):
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    s = _get_state()
    s.processing = True

    try:
        import modules.subtitle_generator as sub_mod
        sub_mod.FONT_SIZE = render_config.get("font_size", 52)
        sub_mod.TEXT_MARGIN_BOTTOM = render_config.get("text_margin_bottom", 180)
        sub_mod.BASE_COLOR = render_config.get("base_color", "#B4B4B4")
        sub_mod.HIGHLIGHT_COLOR = render_config.get("highlight_color", "#FFFF32")

        video_origem = meta["video_origem"]
        inicio = meta["inicio"]
        fim = meta["fim"]
        titulo = meta.get("titulo", cut_id)
        fallback = meta.get("fallback", False)

        if fim - inicio > 90:
            fim = inicio + 90

        if fallback:
            _emit("Aplicando fade/zoom...", 10)
            from modules.zoom_tracker import aplicar_fade
            fade_dur = render_config.get("fade_transition", 0.3)

            caminho_saida = str(PASTA_OUTPUT / f"_tmp_{cut_id}.mp4")

            if fade_dur > 0:
                ok = aplicar_fade(video_origem, caminho_saida, duracao=fade_dur)
            else:
                import shutil
                shutil.copy2(video_origem, caminho_saida)
                ok = True

            if ok and os.path.exists(caminho_saida):
                import shutil
                shutil.move(caminho_saida, video_origem)
                thumb_dir = PASTA_TEMP / "thumbs"
                if thumb_dir.exists():
                    for thumb in thumb_dir.glob(f"{cut_id}*.jpg"):
                        thumb.unlink()
                tamanho_mb = round(os.path.getsize(video_origem) / (1024 * 1024), 1)
                _emit("Pronto!", 100, rerendered={
                    "cut_id": cut_id,
                    "titulo": titulo,
                    "arquivo": os.path.basename(video_origem),
                    "caminho": video_origem,
                    "tamanho_mb": tamanho_mb,
                })
            else:
                _emit("Erro ao processar", 0, error="ffmpeg falhou")
        else:
            _emit("Re-renderizando legenda...", 10)

            _emit("Gerando legendas...", 30)

            from modules.subtitle_generator import gerar_video_com_legendas
            estilo = render_config.get("subtitle_style", "karaoke")

            cut_filename = cut_id if cut_id.endswith(".mp4") else f"{cut_id}.mp4"
            cut_orig_path = None
            for candidate in [PASTA_OUTPUT / cut_filename, *[d / cut_filename for d in PASTA_OUTPUT.iterdir() if d.is_dir()]]:
                if candidate.exists():
                    cut_orig_path = str(candidate)
                    break

            output_dir = str(Path(cut_orig_path).parent) if cut_orig_path else str(PASTA_OUTPUT)

            caminho_saida = gerar_video_com_legendas(
                video_origem,
                meta["segmentos"],
                inicio,
                fim,
                titulo=cut_id,
                estilo=estilo,
                crop_vertical=render_config.get("crop_vertical", True),
                fade_transition=render_config.get("fade_transition", 0.3),
                categoria=meta.get("categoria"),
                output_dir=output_dir,
            )

            if caminho_saida and cut_orig_path and caminho_saida != cut_orig_path:
                import shutil
                shutil.move(caminho_saida, cut_orig_path)
                caminho_saida = cut_orig_path

            if caminho_saida and os.path.exists(caminho_saida):
                thumb_dir = PASTA_TEMP / "thumbs"
                if thumb_dir.exists():
                    for thumb in thumb_dir.glob(f"{cut_id}*.jpg"):
                        thumb.unlink()
                    corte_id = f"corte_{cut_id}"
                    for thumb in thumb_dir.glob(f"{corte_id}*.jpg"):
                        thumb.unlink()
                tamanho_mb = round(os.path.getsize(caminho_saida) / (1024 * 1024), 1)
                _emit("Pronto!", 100, rerendered={
                    "cut_id": cut_id,
                    "titulo": titulo,
                    "arquivo": os.path.basename(caminho_saida),
                    "caminho": caminho_saida,
                    "tamanho_mb": tamanho_mb,
                })
            else:
                _emit("Erro ao re-renderizar", 0, error="ffmpeg falhou")

    except Exception as e:
        _emit(f"Erro: {str(e)}", 0, error=str(e))
    finally:
        s.processing = False
