from fastapi import APIRouter, HTTPException

from app.config.loader import get_registry
from app.config.models import AppConfig

router = APIRouter(prefix="/apps", tags=["apps"])


@router.get("")
def list_apps() -> dict[str, dict[str, AppConfig]]:
    return {"apps": get_registry().list_apps()}


@router.get("/{app_id}")
def get_app(app_id: str) -> AppConfig:
    app = get_registry().get_app(app_id)
    if app is None:
        raise HTTPException(status_code=404, detail="App not found")
    return app
