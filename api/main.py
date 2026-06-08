import os
import sys
import json
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from api.routes_config import router as config_router
from api.routes_process import router as process_router
from api.routes_cuts import router as cuts_router
from api.routes_rerender import router as rerender_router
from api.ws_manager import manager as ws_manager
from api.state import AppState

BASE_DIR = Path(__file__).parent.parent
WEB_DIR = BASE_DIR / "web" / "dist"


@asynccontextmanager
async def lifespan(app):
    asyncio.create_task(ws_manager.broadcast_loop())
    yield


app = FastAPI(title="Dark Channel Bot", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

state = AppState()

app.include_router(config_router, prefix="/api")
app.include_router(process_router, prefix="/api")
app.include_router(cuts_router, prefix="/api")
app.include_router(rerender_router, prefix="/api")


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            if msg.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


if WEB_DIR.exists():
    @app.middleware("http")
    async def spa_middleware(request: Request, call_next):
        response = await call_next(request)
        if response.status_code == 404 and request.method == "GET":
            path = request.url.path.lstrip("/")
            if not path.startswith("api") and not path.startswith("ws"):
                file_path = WEB_DIR / path
                if file_path.exists() and file_path.is_file():
                    return FileResponse(str(file_path))
                return FileResponse(str(WEB_DIR / "index.html"))
        return response

    app.mount("/assets", StaticFiles(directory=str(WEB_DIR / "assets")), name="assets")
