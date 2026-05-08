from fastapi import APIRouter

from app.db.session import check_db
from app.files.storage import ensure_bucket_exists
from app.settings import get_settings

router = APIRouter(tags=["health"])


def check_storage() -> bool:
    try:
        ensure_bucket_exists()
        return True
    except Exception:
        return False


@router.get("/health")
def health() -> dict[str, str]:
    settings = get_settings()
    storage_status = "unknown"
    if settings.storage_health_enabled:
        storage_status = "ok" if check_storage() else "error"
    return {
        "status": "ok",
        "version": settings.version,
        "host": settings.host,
        "db": "ok" if check_db() else "error",
        "storage": storage_status,
    }
