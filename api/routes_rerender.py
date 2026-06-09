import os
import sys
import io
import re
import json
import threading
import subprocess
from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from typing import Optional

from api.state import PASTA_OUTPUT, PASTA_TEMP
from api.routes_process import _get_state, _get_loop, _emit
from api.ws_manager import manager as ws_manager

router = APIRouter()


@router.post("/cut/{cut_id}/preview")
async def preview_subtitle(cut_id: str, body: dict):
    from urllib.parse import unquote
    cut_id = unquote(cut_id)

    meta = _get_cut_data(cut_id)
    if not meta:
        return {"error": f"cut not found: {cut_id}"}

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

    img = sub_mod._generate_preview_frame(cut_id, meta, estilo, crop)
    if img is None:
        return {"error": "failed to generate preview"}

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    buf.seek(0)

    return StreamingResponse(buf, media_type="image/jpeg")


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

    for rpt_path in sorted(PASTA_OUTPUT.glob("relatorio_cortes_*.json"), reverse=True):
        try:
            with open(rpt_path, "r", encoding="utf-8") as f:
                rpt = json.load(f)
            video_origem = rpt.get("video_origem", "")
            if not video_origem or not Path(video_origem).exists():
                continue
            for c in rpt.get("cortes", []):
                if c.get("status") != "ok":
                    continue
                titulo = c.get("titulo", "")
                if titulo in cut_titulo or cut_titulo in titulo:
                    transc_path = PASTA_TEMP / "transcricao.json"
                    if not transc_path.exists():
                        continue
                    with open(transc_path, "r", encoding="utf-8") as f:
                        transc = json.load(f)
                    inicio = c.get("inicio", 0)
                    fim = c.get("fim", 0)
                    segs = [
                        seg for seg in transc.get("segmentos", [])
                        if seg["fim"] >= inicio and seg["inicio"] <= fim
                    ]
                    return {
                        "video_origem": video_origem,
                        "inicio": inicio,
                        "fim": fim,
                        "titulo": titulo,
                        "segmentos": segs,
                    }
        except Exception:
            continue

    transc_path = PASTA_TEMP / "transcricao.json"
    if not transc_path.exists():
        return None

    cut_path = PASTA_OUTPUT / cut_filename
    if not cut_path.exists():
        return None

    with open(transc_path, "r", encoding="utf-8") as f:
        transc = json.load(f)

    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(cut_path)],
            capture_output=True, text=True, timeout=10,
        )
        duracao = float(probe.stdout.strip())
    except Exception:
        return None

    return {
        "video_origem": str(cut_path),
        "inicio": 0,
        "fim": duracao,
        "titulo": cut_id,
        "segmentos": transc.get("segmentos", []),
        "fallback": True,
    }


@router.get("/cut/{cut_id}")
async def get_cut_meta(cut_id: str):
    meta = _get_cut_data(cut_id)
    if not meta:
        return {"error": "not found"}
    return meta


@router.post("/cut/{cut_id}/rerender")
async def rerender_cut(cut_id: str, body: dict):
    from urllib.parse import unquote
    cut_id = unquote(cut_id)

    meta = _get_cut_data(cut_id)
    if not meta:
        return {"error": "cut not found"}

    s = _get_state()
    if s.processing:
        return {"error": "already processing"}

    import asyncio
    global _main_loop
    _main_loop = asyncio.get_running_loop()

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
            nome_saida = re.sub(r'[?#%&\\<>|*]', '', titulo.replace(" ", "_").replace("/", "_"))[:50] + "_v3"
            caminho_saida = str(PASTA_OUTPUT / f"corte_{nome_saida}.mp4")

            if fade_dur > 0:
                ok = aplicar_fade(video_origem, caminho_saida, duracao=fade_dur)
            else:
                import shutil
                shutil.copy2(video_origem, caminho_saida)
                ok = True

            if ok and os.path.exists(caminho_saida):
                tamanho_mb = round(os.path.getsize(caminho_saida) / (1024 * 1024), 1)
                _emit("Pronto!", 100, rerendered={
                    "cut_id": cut_id,
                    "titulo": titulo,
                    "arquivo": os.path.basename(caminho_saida),
                    "caminho": caminho_saida,
                    "tamanho_mb": tamanho_mb,
                })
            else:
                _emit("Erro ao processar", 0, error="ffmpeg falhou")
        else:
            _emit("Re-renderizando legenda...", 10)

            _emit("Gerando legendas...", 30)

            from modules.subtitle_generator import gerar_video_com_legendas
            estilo = render_config.get("subtitle_style", "karaoke")

            caminho_saida = gerar_video_com_legendas(
                video_origem,
                meta["segmentos"],
                inicio,
                fim,
                titulo=f"{titulo}_v2",
                estilo=estilo,
                crop_vertical=render_config.get("crop_vertical", True),
                fade_transition=render_config.get("fade_transition", 0.3),
            )

            if caminho_saida and os.path.exists(caminho_saida):
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
