from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.admin.routes import router as admin_router
from app.auth.routes import router as auth_router
from app.backups.routes import router as backups_router
from app.config.routes import router as config_router
from app.db.init_db import init_db
from app.files.routes import router as files_router
from app.files.storage import ensure_bucket_exists
from app.health.routes import router as health_router
from app.records.routes import router as records_router
from app.settings import get_settings


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    init_db()
    if get_settings().minio_auto_init:
        try:
            ensure_bucket_exists()
        except Exception:
            pass
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="LabBox Backend", version=settings.version, lifespan=lifespan)
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type"],
            allow_credentials=False,
        )
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
    app.include_router(health_router, prefix="/api")
    app.include_router(config_router, prefix="/api")
    app.include_router(auth_router)
    app.include_router(backups_router)
    app.include_router(files_router)
    app.include_router(records_router)
    app.include_router(admin_router)
    return app


app = create_app()
