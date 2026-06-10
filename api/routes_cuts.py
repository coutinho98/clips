import os
import json
from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import FileResponse
from api.state import PASTA_OUTPUT, PASTA_TEMP

router = APIRouter()


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
    cuts = []
    if not PASTA_OUTPUT.exists():
        return {"cuts": cuts}

    all_files = list(PASTA_OUTPUT.glob("corte_*.mp4"))
    for d in PASTA_OUTPUT.iterdir():
        if d.is_dir():
            all_files.extend(d.glob("corte_*.mp4"))

    for f in sorted(all_files, key=lambda x: x.stat().st_mtime, reverse=True):
        size_mb = f.stat().st_size / (1024 * 1024)
        nome = f.stem.replace("corte_", "")

        duracao = 0
        try:
            import subprocess
            probe = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(f)],
                capture_output=True, text=True, timeout=10,
            )
            duracao = float(probe.stdout.strip())
        except Exception:
            pass

        score = 0
        titulo = nome
        meta_path = PASTA_TEMP / f"{f.stem}_meta.json"
        if meta_path.exists():
            try:
                with open(meta_path, "r", encoding="utf-8") as mf:
                    meta = json.loads(mf.read())
                score = meta.get("score", 0)
                if meta.get("titulo"):
                    titulo = meta["titulo"]
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
            "pasta": f.parent.name if f.parent != PASTA_OUTPUT else "",
        })

    return {"cuts": cuts}


@router.get("/cuts/{filename}")
async def download_cut(filename: str):
    filepath = PASTA_OUTPUT / filename
    if not filepath.exists():
        for d in PASTA_OUTPUT.iterdir():
            if d.is_dir():
                candidate = d / filename
                if candidate.exists():
                    filepath = candidate
                    break
    if not filepath.exists():
        return {"error": "not found"}
    return FileResponse(
        str(filepath),
        media_type="video/mp4",
    )


@router.get("/cuts/{filename}/download")
async def download_cut_file(filename: str):
    filepath = PASTA_OUTPUT / filename
    if not filepath.exists():
        for d in PASTA_OUTPUT.iterdir():
            if d.is_dir():
                candidate = d / filename
                if candidate.exists():
                    filepath = candidate
                    break
    if not filepath.exists():
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
