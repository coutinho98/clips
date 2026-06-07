from fastapi import APIRouter
from api.state import DEFAULTS

router = APIRouter()


@router.get("/config")
async def get_config():
    from api.routes_process import _get_state
    s = _get_state()
    return {"config": s.config, "defaults": DEFAULTS}


@router.post("/config")
async def update_config(body: dict):
    from api.routes_process import _get_state
    s = _get_state()
    s.update_config(body)
    return {"config": s.config}


@router.post("/config/reset")
async def reset_config():
    from api.routes_process import _get_state
    s = _get_state()
    s.config = dict(DEFAULTS)
    s.save_config()
    return {"config": s.config}
