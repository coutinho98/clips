import sys
import os
import json
import threading
import asyncio
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form
from typing import Optional

from api.state import AppState, PASTA_OUTPUT, PASTA_TEMP
from api.ws_manager import manager as ws_manager

router = APIRouter()

state: Optional[AppState] = None
_main_loop: Optional[asyncio.AbstractEventLoop] = None


def _get_state():
    global state
    if state is None:
        from api.main import state as s
        state = s
    return state


def _get_loop():
    global _main_loop
    if _main_loop is None or _main_loop.is_closed():
        try:
            _main_loop = asyncio.get_running_loop()
        except RuntimeError:
            pass
    return _main_loop


def _emit(step, progress, **extra):
    s = _get_state()
    s.current_step = step
    s.progress = progress
    data = {
        "type": "progress",
        "step": step,
        "progress": progress,
        **extra,
    }
    loop = _get_loop()
    if loop and loop.is_running():
        asyncio.run_coroutine_threadsafe(ws_manager.send(data), loop)
    else:
        ws_manager._queue.put_nowait(data)


class ProgressHook:
    def __init__(self):
        self.steps = {
            "download": (1, 6),
            "audio": (2, 6),
            "transcricao": (3, 6),
            "picos_audio": (4, 6),
            "highlights": (5, 6),
            "cortes": (6, 6),
        }

    def emit(self, step_name, msg=""):
        info = self.steps.get(step_name, (0, 6))
        step_num, total = info
        pct = (step_num / total) * 100
        _emit(f"[{step_num}/{total}] {msg}", pct)


def _run_pipeline(url: Optional[str], video_path: Optional[str], config: dict):
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

    s = _get_state()
    s.processing = True
    hook = ProgressHook()

    try:
        import modules.subtitle_generator as sub_mod
        sub_mod.FONT_SIZE = config.get("font_size", 52)
        sub_mod.TEXT_MARGIN_BOTTOM = config.get("text_margin_bottom", 180)

        from modules.cache import gerar_job_id, salvar_cache, tem_etapa, obter_etapa
        from modules.live_downloader import baixar_live
        from modules.audio_analyzer import extrair_audio_do_video, detectar_momentos_interessantes
        from modules.transcriber import transcrever_audio, salvar_transcricao
        from modules.heuristic_detector import detectar_highlights_heuristico
        from modules.clip_extractor import extrair_multiplos_cortes

        hook.emit("download", "Baixando vídeo...")
        job_id = gerar_job_id(url, video_path)

        if url and not video_path:
            caminho_video = baixar_live(url)
            if not caminho_video:
                _emit("Erro ao baixar", 0, error="Falha no download")
                return
        else:
            caminho_video = video_path

        hook.emit("audio", "Extraindo áudio...")
        caminho_audio = extrair_audio_do_video(caminho_video)
        if not caminho_audio:
            _emit("Erro ao extrair áudio", 0, error="Falha no áudio")
            return

        hook.emit("transcricao", "Transcrevendo áudio...")
        transcricao = transcrever_audio(
            caminho_audio,
            metodo="local",
            modelo=config.get("whisper_model", "small"),
        )
        if not transcricao:
            _emit("Erro na transcrição", 0, error="Transcrição falhou")
            return
        salvar_transcricao(transcricao)

        hook.emit("picos_audio", "Analisando áudio...")
        momentos_audio = detectar_momentos_interessantes(caminho_audio)

        hook.emit("highlights", "Detectando melhores momentos...")
        max_cuts = config.get("max_cuts", 5)
        detect_method = config.get("detect_method", "ia")
        cortes = []

        if detect_method in ("heuristicas", "ambos"):
            cortes_h = detectar_highlights_heuristico(
                transcricao, momentos_audio, max_cortes=max_cuts
            )
            cortes.extend(cortes_h)

        if detect_method in ("ia", "ambos"):
            try:
                from modules.highlights_detector import detectar_highlights, _usar_ollama
                from config import OPENAI_API_KEY
                if _usar_ollama() or OPENAI_API_KEY:
                    cortes_ia = detectar_highlights(
                        transcricao, picos_audio=momentos_audio, max_cortes=max_cuts
                    )
                    cortes.extend(cortes_ia)
            except Exception as e:
                _emit("IA falhou", 50, warning=str(e))

        from live_clipper import _remover_duplicatas
        cortes = _remover_duplicatas(cortes)
        cortes = sorted(cortes, key=lambda x: x.get("score_viral") or 0, reverse=True)
        cortes = cortes[:max_cuts]

        if not cortes:
            _emit("Nenhum corte encontrado", 0, error="Sem cortes")
            return

        _emit(f"Gerando {len(cortes)} cortes...", 85)
        resultados = extrair_multiplos_cortes(
            caminho_video,
            cortes,
            crop_vertical=config.get("crop_vertical", True),
            adicionar_legenda=True,
            transcricao=transcricao,
            estilo_legenda=config.get("subtitle_style", "karaoke"),
            zoom_dinamico=config.get("zoom_dinamico", False),
            fade_transition=config.get("fade_transition", 0.0),
        )

        import json as _json
        cuts_data = []
        for i, r in enumerate(resultados):
            if r["status"] == "ok":
                import os as _os
                cut_id = f"cut_{i}_{int(r['inicio'])}"

                segs_do_corte = []
                for seg in transcricao.get("segmentos", []):
                    if seg["fim"] >= r["inicio"] and seg["inicio"] <= r["fim"]:
                        segs_do_corte.append(seg)

                cut_meta_path = PASTA_TEMP / f"{cut_id}_meta.json"
                with open(cut_meta_path, "w", encoding="utf-8") as f:
                    _json.dump({
                        "video_origem": caminho_video,
                        "inicio": r["inicio"],
                        "fim": r["fim"],
                        "titulo": r["titulo"],
                        "segmentos": segs_do_corte,
                    }, f, ensure_ascii=False)

                cuts_data.append({
                    "cut_id": cut_id,
                    "titulo": r["titulo"],
                    "arquivo": _os.path.basename(r["caminho"]),
                    "caminho": r["caminho"],
                    "inicio": r["inicio"],
                    "fim": r["fim"],
                    "duracao": r["duracao"],
                    "score": r.get("score", 0),
                    "tamanho_mb": round(_os.path.getsize(r["caminho"]) / (1024 * 1024), 1),
                    "tags": r.get("tags", []),
                })

        _emit("Pronto!", 100, cuts=cuts_data)

    except Exception as e:
        _emit(f"Erro: {str(e)}", 0, error=str(e))
    finally:
        s.processing = False


@router.post("/process")
async def process_video(
    url: Optional[str] = Form(None),
    local_path: Optional[str] = Form(None),
    video: Optional[UploadFile] = File(None),
):
    s = _get_state()
    if s.processing:
        return {"status": "already_processing", "step": s.current_step}

    config = s.config

    video_path = None
    if local_path and os.path.exists(local_path):
        video_path = local_path
    elif video:
        save_path = PASTA_TEMP / video.filename
        with open(save_path, "wb") as f:
            content = await video.read()
            f.write(content)
        video_path = str(save_path)

    if not url and not video_path:
        return {"status": "error", "message": "Forneça uma URL ou arquivo de vídeo"}

    global _main_loop
    _main_loop = asyncio.get_running_loop()

    thread = threading.Thread(
        target=_run_pipeline,
        args=(url, video_path, config),
        daemon=True,
    )
    thread.start()

    return {"status": "started", "config": config}


@router.get("/status")
async def get_status():
    s = _get_state()
    return {
        "processing": s.processing,
        "progress": s.progress,
        "step": s.current_step,
    }
