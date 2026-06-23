import os
import json
import time
import asyncio
import subprocess
from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse
from api.state import PASTA_OUTPUT, PASTA_TEMP

router = APIRouter()

_duration_cache = {}
_DURATION_CACHE_TTL = 300


def _get_duration_cached(filepath):
    now = time.time()
    key = str(filepath)
    if key in _duration_cache:
        cached_dur, cached_time = _duration_cache[key]
        if now - cached_time < _DURATION_CACHE_TTL:
            return cached_dur
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(filepath)],
            capture_output=True, text=True, timeout=10,
        )
        dur = float(probe.stdout.strip())
        _duration_cache[key] = (dur, now)
        return dur
    except Exception:
        return 0


@router.get("/videos")
async def list_local_videos():
    videos = []
    if not PASTA_TEMP.exists():
        return {"videos": videos}

    extensoes = {".mp4", ".mkv", ".ts", ".avi", ".mov"}
    for f in sorted(PASTA_TEMP.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if f.suffix.lower() not in extensoes:
            continue
        if f.name.startswith("corte_"):
            continue
        size_mb = f.stat().st_size / (1024 * 1024)
        videos.append({
            "arquivo": f.name,
            "caminho": str(f),
            "tamanho_mb": round(size_mb, 1),
        })

    return {"videos": videos}


@router.get("/cuts")
async def list_cuts():
    return await asyncio.to_thread(_list_cuts_sync)


def _list_cuts_sync():
    cuts = []
    if not PASTA_OUTPUT.exists():
        return {"cuts": cuts}

    all_files = list(PASTA_OUTPUT.glob("*.mp4"))
    for d in PASTA_OUTPUT.iterdir():
        if d.is_dir():
            all_files.extend(d.glob("*.mp4"))
            for sub in d.iterdir():
                if sub.is_dir():
                    all_files.extend(sub.glob("*.mp4"))

    for f in sorted(all_files, key=lambda x: x.stat().st_mtime, reverse=True):
        size_mb = f.stat().st_size / (1024 * 1024)
        nome = f.stem
        nome = nome.replace("corte_", "") if nome.startswith("corte_") else nome

        duracao = _get_duration_cached(f)

        if f.parent.parent == PASTA_OUTPUT:
            pasta = f.parent.name
        elif f.parent.parent.parent == PASTA_OUTPUT:
            pasta = f.parent.parent.name
        else:
            pasta = ""

        score = 0
        titulo = nome
        tags = []
        meta_path = PASTA_TEMP / f"{f.stem}_meta.json"
        if meta_path.exists():
            try:
                with open(meta_path, "r", encoding="utf-8") as mf:
                    meta = json.loads(mf.read())
                score = meta.get("score", 0)
                if meta.get("titulo"):
                    titulo = meta["titulo"]
                tags = meta.get("tags", [])
            except Exception:
                pass

        cuts.append({
            "cut_id": f.stem,
            "titulo": titulo,
            "arquivo": f.name,
            "caminho": str(f),
            "tamanho_mb": round(size_mb, 1),
            "duracao": duracao,
            "score": score,
            "tags": tags,
            "pasta": pasta,
        })

    return {"cuts": cuts}


def _find_cut_file(filename: str) -> Path | None:
    filepath = PASTA_OUTPUT / filename
    if filepath.exists():
        return filepath
    for d in PASTA_OUTPUT.iterdir():
        if d.is_dir():
            candidate = d / filename
            if candidate.exists():
                return candidate
            for sub in d.iterdir():
                if sub.is_dir():
                    candidate = sub / filename
                    if candidate.exists():
                        return candidate
    return None


@router.get("/cuts/{filename}/thumb")
async def get_cut_thumb(filename: str):
    import io
    filepath = _find_cut_file(filename)
    if not filepath:
        return FileResponse(str(PASTA_OUTPUT / "placeholder.jpg")) if (PASTA_OUTPUT / "placeholder.jpg").exists() else JSONResponse({"error": "not found"}, status_code=404)

    thumb_dir = PASTA_TEMP / "thumbs"
    thumb_dir.mkdir(parents=True, exist_ok=True)
    thumb_path = thumb_dir / f"{filepath.stem}.jpg"

    if not thumb_path.exists():
        def _gen_thumb():
            dur = _get_duration_cached(filepath)
            ts = max(0.5, dur * 0.1) if dur > 0 else 1.0
            subprocess.run(
                ["ffmpeg", "-y", "-v", "quiet", "-ss", str(ts),
                 "-i", str(filepath), "-vframes", "1",
                 "-vf", "scale=320:-1", "-q:v", "5",
                 str(thumb_path)],
                capture_output=True, timeout=15,
            )
        await asyncio.to_thread(_gen_thumb)

    if thumb_path.exists():
        return FileResponse(str(thumb_path), media_type="image/jpeg")
    return JSONResponse({"error": "thumb failed"}, status_code=500)


@router.get("/cuts/{filename}")
async def download_cut(filename: str):
    filepath = _find_cut_file(filename)
    if not filepath:
        return {"error": "not found"}
    return FileResponse(
        str(filepath),
        media_type="video/mp4",
    )


@router.get("/cuts/{filename}/download")
async def download_cut_file(filename: str):
    filepath = _find_cut_file(filename)
    if not filepath:
        return {"error": "not found"}
    return FileResponse(
        str(filepath),
        media_type="video/mp4",
        filename=filename,
    )


@router.get("/reports")
async def list_reports():
    reports = []
    if not PASTA_OUTPUT.exists():
        return {"reports": reports}

    for f in sorted(PASTA_OUTPUT.glob("relatorio_*.json"), key=lambda x: x.stat().st_mtime, reverse=True)[:10]:
        reports.append({
            "arquivo": f.name,
            "data": f.stem.replace("relatorio_cortes_", ""),
        })

    return {"reports": reports}
