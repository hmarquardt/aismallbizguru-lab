import json
import uuid
from typing import Any
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Cookie, Depends, Form, HTTPException, Query, Request, Response, status
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from sqlalchemy import func, select
from starlette.datastructures import UploadFile

from app.auth.password import verify_password
from app.auth.tokens import generate_token, masked_token
from app.backups.runner import BackupRunError, run_backup_now
from app.config.loader import get_registry
from app.config.models import FieldConfig, FieldType
from app.db.models import ApiTokenModel, BackupRunModel, FileModel, RecordModel, utc_now
from app.db.session import get_session_factory
from app.files.service import FileServiceError, create_file, delete_file_record, get_file_metadata, list_files, rename_file_record
from app.files.storage import StorageError, get_file
from app.proxy.service import (
    ProxyError,
    create_source,
    default_config_json,
    fetch_source,
    get_source_by_id,
    list_sources as list_proxy_sources,
    preview_body,
    soft_delete_source,
    source_to_dict,
    update_source,
)
from app.records.service import RecordError, create_record, get_record, list_records as list_resource_records, soft_delete_record, update_record
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


def token_presets() -> list[dict[str, str]]:
    return [
        {
            "app_id": app_id,
            "title": app_config.title,
            "scopes": json.dumps({app_id: ["read", "write"]}),
        }
        for app_id, app_config in get_registry().list_apps().items()
    ]


def parse_token_scopes(raw_scopes: str) -> dict[str, list[str]]:
    raw_scopes = raw_scopes.strip()
    if not raw_scopes:
        return {}

    if raw_scopes.startswith("{"):
        try:
            parsed = json.loads(raw_scopes)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Scopes JSON is invalid: {exc.msg}") from exc
        return normalize_scope_mapping(parsed)

    scopes: dict[str, list[str]] = {}
    for part in raw_scopes.replace("\n", ",").split(","):
        item = part.strip()
        if not item:
            continue
        if ":" not in item:
            raise ValueError("Scope shorthand must use app:level, for example top-hat-ferals:write")
        app_id, level = [piece.strip() for piece in item.split(":", 1)]
        if not app_id or not level:
            raise ValueError("Scope shorthand must include both app and level")
        add_scope_level(scopes, app_id, level)
    return scopes


def normalize_scope_mapping(parsed: Any) -> dict[str, list[str]]:
    if not isinstance(parsed, dict):
        raise ValueError("Scopes must be a JSON object")

    scopes: dict[str, list[str]] = {}
    for app_id, levels in parsed.items():
        if not isinstance(app_id, str) or not app_id:
            raise ValueError("Scope app IDs must be non-empty strings")
        if isinstance(levels, str):
            add_scope_level(scopes, app_id, levels)
            continue
        if not isinstance(levels, list):
            raise ValueError(f"Scopes for {app_id} must be a string or list")
        for level in levels:
            if not isinstance(level, str):
                raise ValueError(f"Scopes for {app_id} must contain only strings")
            add_scope_level(scopes, app_id, level)
    return scopes


def add_scope_level(scopes: dict[str, list[str]], app_id: str, level: str) -> None:
    level = level.strip()
    if level not in {"read", "write", "*"}:
        raise ValueError("Scope levels must be read, write, or *")
    levels = scopes.setdefault(app_id, [])
    if level not in levels:
        levels.append(level)


def redirect(location: str, response: Response) -> Response:
    response.headers["Location"] = location
    response.status_code = status.HTTP_303_SEE_OTHER
    return response


def wants_json(request: Request) -> bool:
    return request.headers.get("x-requested-with") == "XMLHttpRequest"


def ajax_response(message: str, location: str | None = None, **extra: Any) -> JSONResponse:
    payload = {"ok": True, "message": message}
    if location:
        payload["location"] = location
    payload.update(extra)
    return JSONResponse(payload)


def parse_record_data(resource_config, form: dict[str, Any]) -> dict[str, Any]:
    data: dict[str, Any] = {}
    errors: list[str] = []
    for field_name, field_config in resource_config.fields.items():
        raw_value = form.get(field_name)
        if field_config.type == FieldType.boolean:
            data[field_name] = raw_value in {"on", "true", "1", "yes"}
            continue

        raw_text = str(raw_value).strip() if raw_value is not None else ""
        if field_config.required and raw_text == "":
            errors.append(f"{field_label(field_name, field_config)} is required")
            continue
        if raw_text == "":
            if field_config.default is not None:
                data[field_name] = field_config.default
            continue

        try:
            data[field_name] = parse_field_value(field_config.type, raw_text)
        except ValueError as exc:
            errors.append(f"{field_label(field_name, field_config)}: {exc}")

    if errors:
        raise RecordError("; ".join(errors))
    return data


def parse_field_value(field_type: FieldType, raw_value: str) -> Any:
    if field_type == FieldType.integer:
        return int(raw_value)
    if field_type == FieldType.number:
        return float(raw_value)
    if field_type in {FieldType.json, FieldType.list}:
        value = json.loads(raw_value)
        if field_type == FieldType.list and not isinstance(value, list):
            raise ValueError("must be a JSON list")
        return value
    return raw_value


def field_label(field_name: str, field_config: FieldConfig) -> str:
    return field_config.label or field_name.replace("_", " ").title()


def record_form_values(resource_config, record: RecordModel | None = None) -> dict[str, Any]:
    values: dict[str, Any] = {}
    if record is not None:
        values = json.loads(record.data_json) if isinstance(record.data_json, str) else record.data_json
    return {
        name: format_field_value(config.type, values.get(name, config.default))
        for name, config in resource_config.fields.items()
    }


def format_field_value(field_type: FieldType, value: Any) -> str:
    if value is None:
        return ""
    if field_type in {FieldType.json, FieldType.list}:
        return json.dumps(value, indent=2)
    return str(value)


def json_display_value(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True)


def parse_json_object(raw_value: str, label: str = "JSON") -> dict:
    try:
        value = json.loads(raw_value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} is invalid: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def proxy_source_view(source) -> dict:
    data = source_to_dict(source)
    data["config_json"] = json.dumps(data["config"], indent=2, sort_keys=True)
    return data


def parse_sample_query(raw_value: str) -> list[tuple[str, str]]:
    from urllib.parse import parse_qsl

    raw_value = raw_value.strip()
    if raw_value.startswith("?"):
        raw_value = raw_value[1:]
    return parse_qsl(raw_value, keep_blank_values=True)


def content_disposition_attachment(filename: str) -> str:
    fallback = "".join(
        char if 32 <= ord(char) < 127 and char not in {'"', "\\", ";"} else "_"
        for char in filename
    ).strip()
    if not fallback:
        fallback = "download"
    return f"attachment; filename=\"{fallback}\"; filename*=UTF-8''{quote(filename)}"


def app_filter_options() -> list[dict[str, str]]:
    return [
        {"app_id": app_id, "title": app_config.title}
        for app_id, app_config in get_registry().list_apps().items()
    ]


def token_display(token_id: str | None, token_names: dict[str, str]) -> str:
    if not token_id:
        return "Admin"
    token_name = token_names.get(token_id)
    if token_name:
        return f"{token_name} ({token_id})"
    return f"Deleted token ({token_id})"


def token_name_map(token_ids: set[str]) -> dict[str, str]:
    if not token_ids:
        return {}
    session = get_session_factory()()
    try:
        tokens = session.scalars(select(ApiTokenModel).where(ApiTokenModel.id.in_(token_ids))).all()
        return {token.id: token.name for token in tokens}
    finally:
        session.close()


def get_record_or_404(record_id: str) -> RecordModel:
    record = get_record(record_id)
    if record is None or record.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Record not found")
    return record


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


@router.get("/apps/{app_id}/{resource}", response_class=HTMLResponse)
def resource_records(app_id: str, resource: str, _: Annotated[str, Depends(require_admin)]):
    registry = get_registry()
    app_config = registry.get_app(app_id)
    resource_config = registry.get_resource(app_id, resource)
    if app_config is None or resource_config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    records = list_resource_records(app_id, resource)
    token_names = token_name_map({r.created_by_token_id for r in records if r.created_by_token_id})
    return render("resource_records.html", app_id=app_id, app=app_config,
                  resource=resource, resource_config=resource_config,
                  records=[{
                      "id": r.id,
                      "data": json.loads(r.data_json) if isinstance(r.data_json, str) else r.data_json,
                      "data_json": json_display_value(
                          json.loads(r.data_json) if isinstance(r.data_json, str) else r.data_json
                      ),
                      "created_by": token_display(r.created_by_token_id, token_names),
                      "created_at": r.created_at,
                      "updated_at": r.updated_at,
                  } for r in records])


@router.get("/apps/{app_id}/{resource}/new", response_class=HTMLResponse)
def new_record_form(app_id: str, resource: str, _: Annotated[str, Depends(require_admin)]):
    registry = get_registry()
    app_config = registry.get_app(app_id)
    resource_config = registry.get_resource(app_id, resource)
    if app_config is None or resource_config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    return render("record_form.html", mode="create", app_id=app_id, app=app_config,
                  resource=resource, resource_config=resource_config,
                  values=record_form_values(resource_config), error=None, record=None)


@router.post("/apps/{app_id}/{resource}/new")
async def create_record_page(app_id: str, resource: str, request: Request, response: Response,
                             _: Annotated[str, Depends(require_admin)]):
    registry = get_registry()
    app_config = registry.get_app(app_id)
    resource_config = registry.get_resource(app_id, resource)
    if app_config is None or resource_config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")

    form = dict(await request.form())
    try:
        record = create_record(app_id, resource, parse_record_data(resource_config, form))
    except RecordError as exc:
        if wants_json(request):
            return JSONResponse({"ok": False, "message": str(exc)}, status_code=status.HTTP_400_BAD_REQUEST)
        return render("record_form.html", mode="create", app_id=app_id, app=app_config,
                      resource=resource, resource_config=resource_config,
                      values=form, error=str(exc), record=None)
    if wants_json(request):
        return ajax_response("Record created", f"/admin/records/{record.id}", id=record.id)
    return redirect(f"/admin/records/{record.id}", response)


@router.get("/records", response_class=HTMLResponse)
def list_records(
    _: Annotated[str, Depends(require_admin)],
    app_id: Annotated[str | None, Query()] = None,
    resource: Annotated[str | None, Query()] = None,
):
    session = get_session_factory()()
    try:
        query = select(RecordModel).where(RecordModel.deleted_at.is_(None))
        if app_id:
            query = query.where(RecordModel.app_id == app_id)
        if resource:
            query = query.where(RecordModel.resource == resource)
        records = session.scalars(
            query.order_by(RecordModel.created_at.desc()).limit(100)
        ).all()
    finally:
        session.close()

    data = []
    token_names = token_name_map({r.created_by_token_id for r in records if r.created_by_token_id})
    for r in records:
        rec_data = json.loads(r.data_json) if isinstance(r.data_json, str) else r.data_json
        data.append({"id": r.id, "app_id": r.app_id, "resource": r.resource,
                     "data": rec_data, "data_json": json_display_value(rec_data),
                     "created_by": token_display(r.created_by_token_id, token_names),
                     "created_at": r.created_at})
    return render(
        "records.html",
        records=data,
        apps=app_filter_options(),
        selected_app_id=app_id or "",
        selected_resource=resource or "",
    )


@router.get("/records/{record_id}", response_class=HTMLResponse)
def record_detail(record_id: str, _: Annotated[str, Depends(require_admin)]):
    record = get_record_or_404(record_id)
    registry = get_registry()
    app_config = registry.get_app(record.app_id)
    resource_config = registry.get_resource(record.app_id, record.resource)
    if app_config is None or resource_config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not configured")

    files = list_files(record.app_id, record.resource, record.id) if resource_config.files.enabled else []
    data = json.loads(record.data_json) if isinstance(record.data_json, str) else record.data_json
    token_ids = {record.created_by_token_id} if record.created_by_token_id else set()
    token_ids.update(f.created_by_token_id for f in files if f.created_by_token_id)
    token_names = token_name_map(token_ids)
    return render("record_detail.html", record=record, data=data, app=app_config,
                  resource_config=resource_config, files=[{
                      "id": f.id,
                      "object_key": f.object_key,
                      "filename": f.filename,
                      "content_type": f.content_type,
                      "size_bytes": f.size_bytes,
                      "created_by": token_display(f.created_by_token_id, token_names),
                  } for f in files],
                  created_by=token_display(record.created_by_token_id, token_names))


@router.get("/records/{record_id}/edit", response_class=HTMLResponse)
def edit_record_form(record_id: str, _: Annotated[str, Depends(require_admin)]):
    record = get_record_or_404(record_id)
    registry = get_registry()
    app_config = registry.get_app(record.app_id)
    resource_config = registry.get_resource(record.app_id, record.resource)
    if app_config is None or resource_config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not configured")
    return render("record_form.html", mode="edit", app_id=record.app_id, app=app_config,
                  resource=record.resource, resource_config=resource_config,
                  values=record_form_values(resource_config, record), error=None, record=record)


@router.post("/records/{record_id}")
async def update_record_page(record_id: str, request: Request, response: Response,
                             _: Annotated[str, Depends(require_admin)]):
    record = get_record_or_404(record_id)
    registry = get_registry()
    app_config = registry.get_app(record.app_id)
    resource_config = registry.get_resource(record.app_id, record.resource)
    if app_config is None or resource_config is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not configured")

    form = dict(await request.form())
    try:
        update_record(record_id, parse_record_data(resource_config, form))
    except RecordError as exc:
        if wants_json(request):
            return JSONResponse({"ok": False, "message": str(exc)}, status_code=status.HTTP_400_BAD_REQUEST)
        return render("record_form.html", mode="edit", app_id=record.app_id, app=app_config,
                      resource=record.resource, resource_config=resource_config,
                      values=form, error=str(exc), record=record)
    if wants_json(request):
        return ajax_response("Record saved", f"/admin/records/{record_id}", id=record_id)
    return redirect(f"/admin/records/{record_id}", response)


@router.post("/records/{record_id}/delete")
def delete_record_page(record_id: str, request: Request, response: Response, _: Annotated[str, Depends(require_admin)]):
    record = get_record_or_404(record_id)
    location = f"/admin/apps/{record.app_id}/{record.resource}"
    try:
        soft_delete_record(record_id)
    except RecordError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if wants_json(request):
        return ajax_response("Record deleted", location)
    return redirect(location, response)


@router.post("/records/{record_id}/files")
async def upload_record_file(record_id: str, request: Request, response: Response,
                             _: Annotated[str, Depends(require_admin)]):
    record = get_record_or_404(record_id)
    form = await request.form()
    uploaded = form.get("file")
    if not isinstance(uploaded, UploadFile):
        if wants_json(request):
            return JSONResponse({"ok": False, "message": "File is required"}, status_code=status.HTTP_400_BAD_REQUEST)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File is required")
    try:
        file_model = create_file(record.app_id, record.resource, record.id, uploaded.filename or "unnamed",
                                 uploaded.content_type or "application/octet-stream", await uploaded.read())
    except FileServiceError as exc:
        if wants_json(request):
            return JSONResponse({"ok": False, "message": str(exc)}, status_code=status.HTTP_400_BAD_REQUEST)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if wants_json(request):
        return ajax_response("File uploaded", f"/admin/records/{record_id}", id=file_model.id)
    return redirect(f"/admin/records/{record_id}", response)


@router.get("/files", response_class=HTMLResponse)
def list_files_admin(
    _: Annotated[str, Depends(require_admin)],
    app_id: Annotated[str | None, Query()] = None,
    resource: Annotated[str | None, Query()] = None,
):
    session = get_session_factory()()
    try:
        query = select(FileModel).where(FileModel.deleted_at.is_(None))
        if app_id:
            query = query.where(FileModel.app_id == app_id)
        if resource:
            query = query.where(FileModel.resource == resource)
        files = session.scalars(
            query.order_by(FileModel.created_at.desc()).limit(100)
        ).all()
    finally:
        session.close()
    token_names = token_name_map({f.created_by_token_id for f in files if f.created_by_token_id})
    return render("files.html", files=[{
        "id": f.id, "app_id": f.app_id, "resource": f.resource,
        "record_id": f.record_id, "filename": f.filename,
        "content_type": f.content_type, "size_bytes": f.size_bytes, "created_at": f.created_at,
        "created_by": token_display(f.created_by_token_id, token_names),
    } for f in files], apps=app_filter_options(), selected_app_id=app_id or "", selected_resource=resource or "")


@router.get("/files/{file_id}/download")
def download_file_admin(file_id: str, _: Annotated[str, Depends(require_admin)]) -> StreamingResponse:
    model = get_file_metadata(file_id)
    if model is None or model.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    try:
        data_stream = get_file(model.object_key)
    except StorageError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))
    return StreamingResponse(
        data_stream,
        media_type=model.content_type or "application/octet-stream",
        headers={"Content-Disposition": content_disposition_attachment(model.filename)},
    )


@router.post("/files/{file_id}/rename")
def rename_file_page(file_id: str, request: Request, response: Response, _: Annotated[str, Depends(require_admin)],
                     filename: Annotated[str, Form()]):
    try:
        model = rename_file_record(file_id, filename)
    except FileServiceError as exc:
        if wants_json(request):
            return JSONResponse({"ok": False, "message": str(exc)}, status_code=status.HTTP_400_BAD_REQUEST)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    location = f"/admin/records/{model.record_id}" if model.record_id else "/admin/files"
    if wants_json(request):
        return ajax_response("File renamed", location, filename=model.filename)
    return redirect(location, response)


@router.post("/files/{file_id}/delete")
def delete_file_page(
    file_id: str,
    request: Request,
    response: Response,
    _: Annotated[str, Depends(require_admin)],
    next_url: Annotated[str, Form()] = "/admin/files",
):
    model = get_file_metadata(file_id)
    if model is None or model.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    location = next_url if next_url.startswith("/") and not next_url.startswith("//") else "/admin/files"
    try:
        delete_file_record(file_id)
    except FileServiceError as exc:
        if wants_json(request):
            return JSONResponse({"ok": False, "message": str(exc)}, status_code=status.HTTP_400_BAD_REQUEST)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if wants_json(request):
        return ajax_response("File deleted", location)
    return redirect(location, response)


@router.get("/proxy-sources", response_class=HTMLResponse)
def proxy_sources_page(
    _: Annotated[str, Depends(require_admin)],
    edit_id: Annotated[str | None, Query()] = None,
):
    sources = [proxy_source_view(source) for source in list_proxy_sources()]
    editing = None
    if edit_id:
        source = get_source_by_id(edit_id)
        if source is None or source.deleted_at is not None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proxy source not found")
        editing = proxy_source_view(source)
    return render(
        "proxy_sources.html",
        sources=sources,
        editing=editing,
        default_config_json=default_config_json(),
        error=None,
        form_values={},
    )


@router.post("/proxy-sources")
def create_proxy_source_page(
    request: Request,
    response: Response,
    _: Annotated[str, Depends(require_admin)],
    name: Annotated[str, Form()],
    slug: Annotated[str, Form()],
    description: Annotated[str, Form()] = "",
    config_json: Annotated[str, Form()] = "",
    enabled: Annotated[str | None, Form()] = None,
    public: Annotated[str | None, Form()] = None,
):
    try:
        source = create_source(
            slug,
            name,
            description,
            enabled is not None,
            public is not None,
            parse_json_object(config_json, "Config JSON"),
        )
    except (ValueError, ProxyError) as exc:
        if wants_json(request):
            return JSONResponse({"ok": False, "message": str(exc)}, status_code=status.HTTP_400_BAD_REQUEST)
        return render(
            "proxy_sources.html",
            sources=[proxy_source_view(source) for source in list_proxy_sources()],
            editing=None,
            default_config_json=default_config_json(),
            error=str(exc),
            form_values=dict(name=name, slug=slug, description=description, config_json=config_json),
        )
    if wants_json(request):
        return ajax_response("Proxy source created", f"/admin/proxy-sources?edit_id={source.id}", id=source.id)
    return redirect(f"/admin/proxy-sources?edit_id={source.id}", response)


@router.post("/proxy-sources/{source_id}")
def update_proxy_source_page(
    source_id: str,
    request: Request,
    response: Response,
    _: Annotated[str, Depends(require_admin)],
    name: Annotated[str, Form()],
    slug: Annotated[str, Form()],
    description: Annotated[str, Form()] = "",
    config_json: Annotated[str, Form()] = "",
    enabled: Annotated[str | None, Form()] = None,
    public: Annotated[str | None, Form()] = None,
):
    try:
        update_source(
            source_id,
            slug=slug,
            name=name,
            description=description,
            enabled=enabled is not None,
            public=public is not None,
            config=parse_json_object(config_json, "Config JSON"),
        )
    except (ValueError, ProxyError) as exc:
        if wants_json(request):
            return JSONResponse({"ok": False, "message": str(exc)}, status_code=status.HTTP_400_BAD_REQUEST)
        source = get_source_by_id(source_id)
        return render(
            "proxy_sources.html",
            sources=[proxy_source_view(source) for source in list_proxy_sources()],
            editing=proxy_source_view(source) if source else None,
            default_config_json=default_config_json(),
            error=str(exc),
            form_values=dict(name=name, slug=slug, description=description, config_json=config_json),
        )
    if wants_json(request):
        return ajax_response("Proxy source saved", f"/admin/proxy-sources?edit_id={source_id}", id=source_id)
    return redirect(f"/admin/proxy-sources?edit_id={source_id}", response)


@router.post("/proxy-sources/{source_id}/clone")
def clone_proxy_source_page(
    source_id: str,
    request: Request,
    response: Response,
    _: Annotated[str, Depends(require_admin)],
):
    source = get_source_by_id(source_id)
    if source is None or source.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proxy source not found")
    try:
        clone = create_source(
            f"{source.slug}-copy",
            f"{source.name} Copy",
            source.description,
            False,
            source.public,
            json.loads(source.config_json),
        )
    except ProxyError as exc:
        if wants_json(request):
            return JSONResponse({"ok": False, "message": str(exc)}, status_code=status.HTTP_400_BAD_REQUEST)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if wants_json(request):
        return ajax_response("Proxy source cloned", f"/admin/proxy-sources?edit_id={clone.id}", id=clone.id)
    return redirect(f"/admin/proxy-sources?edit_id={clone.id}", response)


@router.post("/proxy-sources/{source_id}/delete")
def delete_proxy_source_page(
    source_id: str,
    request: Request,
    response: Response,
    _: Annotated[str, Depends(require_admin)],
):
    try:
        soft_delete_source(source_id)
    except ProxyError as exc:
        if wants_json(request):
            return JSONResponse({"ok": False, "message": str(exc)}, status_code=status.HTTP_400_BAD_REQUEST)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if wants_json(request):
        return ajax_response("Proxy source deleted", "/admin/proxy-sources")
    return redirect("/admin/proxy-sources", response)


@router.post("/proxy-sources/{source_id}/test")
def test_proxy_source_page(
    source_id: str,
    _: Annotated[str, Depends(require_admin)],
    sample_query: Annotated[str, Form()] = "",
) -> JSONResponse:
    source = get_source_by_id(source_id)
    if source is None or source.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proxy source not found")
    try:
        result = fetch_source(source, parse_sample_query(sample_query))
    except ProxyError as exc:
        payload = {"ok": False, "error": exc.message}
        if exc.upstream_url:
            payload["upstream_url"] = exc.upstream_url
        return JSONResponse(payload)
    return JSONResponse({
        "ok": True,
        "upstream_url": result.upstream_url,
        "status_code": result.status_code,
        "content_type": result.content_type,
        "bytes": len(result.body),
        "cache_status": result.cache_status,
        "preview": preview_body(result.body, result.content_type),
    })


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
    } for t in tokens], new_token=new_token, token_presets=token_presets(),
                  scope_error=None, form_name="", form_scopes="")


@router.post("/tokens")
def create_token_page(request: Request, response: Response, _: Annotated[str, Depends(require_admin)],
                      name: Annotated[str, Form()], scopes: Annotated[str, Form()] = ""):
    try:
        scopes_json = parse_token_scopes(scopes)
    except ValueError as exc:
        if wants_json(request):
            return JSONResponse({"ok": False, "message": str(exc)}, status_code=status.HTTP_400_BAD_REQUEST)
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
        } for t in tokens], new_token=None, token_presets=token_presets(),
                      scope_error=str(exc), form_name=name, form_scopes=scopes)

    raw, token_hash = generate_token()
    session = get_session_factory()()
    try:
        model = ApiTokenModel(id=str(uuid.uuid4()), name=name, token_hash=token_hash,
                              scopes_json=json.dumps(scopes_json), created_at=utc_now())
        session.add(model)
        session.commit()
    finally:
        session.close()

    if wants_json(request):
        return ajax_response("Token created. Save it now; it will not be shown again.", "/admin/tokens", token=raw)
    response.headers["Location"] = f"/admin/tokens?new_token={raw}"
    response.status_code = status.HTTP_303_SEE_OTHER
    return response


@router.post("/tokens/{token_id}/revoke")
def revoke_token_page(request: Request, response: Response, token_id: str, _: Annotated[str, Depends(require_admin)]):
    session = get_session_factory()()
    try:
        token = session.scalar(select(ApiTokenModel).where(ApiTokenModel.id == token_id))
        if token:
            token.revoked_at = utc_now()
            session.commit()
    finally:
        session.close()
    if wants_json(request):
        return ajax_response("Token revoked", "/admin/tokens")
    response.headers["Location"] = "/admin/tokens"
    response.status_code = status.HTTP_303_SEE_OTHER
    return response


@router.post("/tokens/{token_id}/delete")
def delete_token_page(request: Request, response: Response, token_id: str, _: Annotated[str, Depends(require_admin)]):
    session = get_session_factory()()
    try:
        token = session.scalar(select(ApiTokenModel).where(ApiTokenModel.id == token_id))
        if token:
            session.delete(token)
            session.commit()
    finally:
        session.close()
    if wants_json(request):
        return ajax_response("Token deleted", "/admin/tokens")
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
