from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.exc import IntegrityError

from app.auth.dependencies import check_scope, get_optional_token
from app.auth.routes import require_admin
from app.db.models import ApiTokenModel
from app.proxy.schemas import (
    ProxySourceCreate,
    ProxySourceOut,
    ProxySourcePatch,
    ProxySourceTestRequest,
)
from app.proxy.service import (
    ProxyError,
    create_source,
    fetch_source,
    get_source_by_id,
    get_source_by_slug,
    list_sources,
    parse_config,
    preview_body,
    soft_delete_source,
    source_to_dict,
    update_source,
)


router = APIRouter(tags=["proxy"])


def proxy_http_exception(error: ProxyError) -> HTTPException:
    return HTTPException(status_code=error.status_code, detail=error.message)


def ensure_runtime_access(source, token: ApiTokenModel | None) -> None:
    config = parse_config(source.config_json)
    if source.public or config.auth.mode == "public":
        return
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing bearer token",
        )
    if config.auth.scope_app:
        check_scope(token, config.auth.scope_app, config.auth.required_scope)


@router.get("/api/proxy/{slug}")
def proxy_get(
    slug: str,
    request: Request,
    token: Annotated[ApiTokenModel | None, Depends(get_optional_token)],
) -> Response:
    source = get_source_by_slug(slug)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proxy source not found")
    try:
        ensure_runtime_access(source, token)
        result = fetch_source(source, request.query_params.multi_items())
    except ProxyError as exc:
        raise proxy_http_exception(exc) from exc
    return Response(
        content=result.body,
        status_code=result.status_code,
        media_type=result.content_type,
        headers={
            "X-LabBox-Proxy-Source": source.slug,
            "X-LabBox-Proxy-Cache": result.cache_status,
        },
    )


@router.get("/api/admin/proxy-sources", response_model=list[ProxySourceOut])
def admin_list_proxy_sources(_: Annotated[None, Depends(require_admin)]) -> list[ProxySourceOut]:
    return [ProxySourceOut.model_validate(source_to_dict(source)) for source in list_sources()]


@router.post("/api/admin/proxy-sources", status_code=status.HTTP_201_CREATED, response_model=ProxySourceOut)
def admin_create_proxy_source(
    body: ProxySourceCreate,
    _: Annotated[None, Depends(require_admin)],
) -> ProxySourceOut:
    try:
        source = create_source(
            body.slug,
            body.name,
            body.description,
            body.enabled,
            body.public,
            body.config,
        )
    except IntegrityError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slug is already in use") from exc
    except ProxyError as exc:
        raise proxy_http_exception(exc) from exc
    return ProxySourceOut.model_validate(source_to_dict(source))


@router.get("/api/admin/proxy-sources/{source_id}", response_model=ProxySourceOut)
def admin_get_proxy_source(
    source_id: str,
    _: Annotated[None, Depends(require_admin)],
) -> ProxySourceOut:
    source = get_source_by_id(source_id)
    if source is None or source.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proxy source not found")
    return ProxySourceOut.model_validate(source_to_dict(source))


@router.patch("/api/admin/proxy-sources/{source_id}", response_model=ProxySourceOut)
def admin_update_proxy_source(
    source_id: str,
    body: ProxySourcePatch,
    _: Annotated[None, Depends(require_admin)],
) -> ProxySourceOut:
    try:
        source = update_source(source_id, **body.model_dump(exclude_unset=True))
    except ProxyError as exc:
        raise proxy_http_exception(exc) from exc
    return ProxySourceOut.model_validate(source_to_dict(source))


@router.delete("/api/admin/proxy-sources/{source_id}")
def admin_delete_proxy_source(
    source_id: str,
    _: Annotated[None, Depends(require_admin)],
) -> dict[str, str]:
    try:
        soft_delete_source(source_id)
    except ProxyError as exc:
        raise proxy_http_exception(exc) from exc
    return {"status": "deleted"}


@router.post("/api/admin/proxy-sources/{source_id}/test")
def admin_test_proxy_source(
    source_id: str,
    body: ProxySourceTestRequest,
    _: Annotated[None, Depends(require_admin)],
) -> dict:
    source = get_source_by_id(source_id)
    if source is None or source.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Proxy source not found")
    try:
        result = fetch_source(source, body.query_params.items())
    except ProxyError as exc:
        payload = {"ok": False, "error": exc.message}
        if exc.upstream_url:
            payload["upstream_url"] = exc.upstream_url
        return payload
    return {
        "ok": True,
        "upstream_url": result.upstream_url,
        "status_code": result.status_code,
        "content_type": result.content_type,
        "bytes": len(result.body),
        "cache_status": result.cache_status,
        "preview": preview_body(result.body, result.content_type),
    }
