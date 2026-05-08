import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Form, HTTPException, Response, status
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select

from app.auth.password import verify_password
from app.auth.tokens import generate_token, masked_token
from app.backups.runner import BackupRunError, run_backup_now
from app.config.loader import get_registry
from app.db.models import ApiTokenModel, BackupRunModel, FileModel, RecordModel, utc_now
from app.db.session import get_session_factory
from app.settings import get_settings
from app.templates import env


router = APIRouter(prefix="/admin", tags=["admin"])
TEMPLATES = env


def require_admin(session: Annotated[str | None, Cookie()] = None) -> str:
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    settings = get_settings()
    if session != settings.admin_session_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
    return session


def render(template_name: str, **context) -> HTMLResponse:
    template = TEMPLATES.get_template(template_name)
    return HTMLResponse(template.render(**context))


@router.get("/login", response_class=HTMLResponse)
def login_page():
    return render("login.html", error=None)


@router.post("/login")
def login(response: Response, password: Annotated[str, Form()]):
    settings = get_settings()
    if not settings.admin_session_secret or not settings.admin_password_hash:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Admin not configured")

    if not verify_password(password, settings.admin_password_hash):
        return render("login.html", error="Invalid password")

    response.set_cookie("session", settings.admin_session_secret, httponly=True, secure=True, samesite="lax", max_age=86400 * 7)
    response.headers["Location"] = "/admin/"
    response.status_code = status.HTTP_303_SEE_OTHER
    return response


@router.get("/", response_class=HTMLResponse)
def dashboard(_: Annotated[str, Depends(require_admin)]):
    settings = get_settings()
    session = get_session_factory()()
    try:
        record_count = session.execute(select(func.count()).select_from(RecordModel).where(RecordModel.deleted_at.is_(None))).scalar() or 0
        file_count = session.execute(select(func.count()).select_from(FileModel).where(FileModel.deleted_at.is_(None))).scalar() or 0
        backup = session.scalars(select(BackupRunModel).order_by(BackupRunModel.started_at.desc()).limit(1)).first()
    finally:
        session.close()

    registry = get_registry()
    configured_apps = len(registry.list_apps())

    return render("dashboard.html", version=settings.version, host=settings.host,
                  app_count=configured_apps, record_count=record_count, file_count=file_count,
                  backup=backup)


@router.get("/apps", response_class=HTMLResponse)
def list_apps(_: Annotated[str, Depends(require_admin)]):
    registry = get_registry()
    return render("apps.html", apps=registry.list_apps())


@router.get("/records", response_class=HTMLResponse)
def list_records(_: Annotated[str, Depends(require_admin)]):
    session = get_session_factory()()
    try:
        records = session.scalars(
            select(RecordModel).where(RecordModel.deleted_at.is_(None))
            .order_by(RecordModel.created_at.desc()).limit(100)
        ).all()
    finally:
        session.close()

    data = []
    for r in records:
        rec_data = json.loads(r.data_json) if isinstance(r.data_json, str) else r.data_json
        data.append({"id": r.id, "app_id": r.app_id, "resource": r.resource,
                     "data": rec_data, "created_at": r.created_at})
    return render("records.html", records=data)


@router.get("/files", response_class=HTMLResponse)
def list_files_admin(_: Annotated[str, Depends(require_admin)]):
    session = get_session_factory()()
    try:
        files = session.scalars(
            select(FileModel).where(FileModel.deleted_at.is_(None))
            .order_by(FileModel.created_at.desc()).limit(100)
        ).all()
    finally:
        session.close()
    return render("files.html", files=[{
        "id": f.id, "app_id": f.app_id, "resource": f.resource,
        "record_id": f.record_id, "filename": f.filename,
        "content_type": f.content_type, "size_bytes": f.size_bytes, "created_at": f.created_at
    } for f in files])


@router.get("/tokens", response_class=HTMLResponse)
def list_tokens_page(_: Annotated[str, Depends(require_admin)], new_token: str | None = None):
    session = get_session_factory()()
    try:
        tokens = session.scalars(select(ApiTokenModel).order_by(ApiTokenModel.created_at.desc())).all()
    finally:
        session.close()
    return render("tokens.html", tokens=[{
        "id": t.id, "name": t.name,
        "masked": masked_token(t.token_hash),
        "scopes": json.loads(t.scopes_json) if t.scopes_json else {},
        "created_at": t.created_at, "revoked_at": t.revoked_at
    } for t in tokens], new_token=new_token)


@router.post("/tokens")
def create_token_page(response: Response, _: Annotated[str, Depends(require_admin)],
                      name: Annotated[str, Form()], scopes: Annotated[str, Form()] = ""):
    scopes_json = {}
    if scopes.strip():
        try:
            scopes_json = json.loads(scopes)
        except json.JSONDecodeError:
            pass

    raw, token_hash = generate_token()
    session = get_session_factory()()
    try:
        model = ApiTokenModel(id=str(uuid.uuid4()), name=name, token_hash=token_hash,
                              scopes_json=json.dumps(scopes_json), created_at=utc_now())
        session.add(model)
        session.commit()
    finally:
        session.close()

    response.headers["Location"] = f"/admin/tokens?new_token={raw}"
    response.status_code = status.HTTP_303_SEE_OTHER
    return response


@router.post("/tokens/{token_id}/revoke")
def revoke_token_page(response: Response, token_id: str, _: Annotated[str, Depends(require_admin)]):
    session = get_session_factory()()
    try:
        token = session.scalar(select(ApiTokenModel).where(ApiTokenModel.id == token_id))
        if token:
            token.revoked_at = utc_now()
            session.commit()
    finally:
        session.close()
    response.headers["Location"] = "/admin/tokens"
    response.status_code = status.HTTP_303_SEE_OTHER
    return response


@router.get("/backups", response_class=HTMLResponse)
def backups_page(_: Annotated[str, Depends(require_admin)]):
    session = get_session_factory()()
    try:
        backup_runs = session.scalars(
            select(BackupRunModel).order_by(BackupRunModel.started_at.desc()).limit(50)
        ).all()
    finally:
        session.close()
    return render("backups.html", backup_runs=[{
        "id": b.id, "status": b.status, "started_at": b.started_at,
        "finished_at": b.finished_at, "snapshot_id": b.snapshot_id,
        "bytes_added": b.bytes_added, "error": b.error
    } for b in backup_runs])


@router.post("/backups/run")
def run_backup_page(response: Response, _: Annotated[str, Depends(require_admin)]):
    try:
        run_backup_now()
    except BackupRunError:
        pass
    response.headers["Location"] = "/admin/backups"
    response.status_code = status.HTTP_303_SEE_OTHER
    return response


@router.post("/logout")
def logout(response: Response, _: Annotated[str, Depends(require_admin)]):
    response.delete_cookie("session")
    response.headers["Location"] = "/admin/login"
    response.status_code = status.HTTP_303_SEE_OTHER
    return response
