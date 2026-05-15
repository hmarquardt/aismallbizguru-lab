import ipaddress
import json
import socket
import uuid
from collections.abc import Iterable
from dataclasses import dataclass

import httpx
from sqlalchemy import select

from app.db.models import ProxySourceModel, utc_now
from app.db.session import get_session_factory
from app.proxy.schemas import DEFAULT_PROXY_CONFIG, ProxySourceConfig


class ProxyError(Exception):
    def __init__(self, message: str, status_code: int = 400, upstream_url: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.upstream_url = upstream_url


@dataclass
class ProxyResult:
    status_code: int
    content_type: str
    body: bytes
    upstream_url: str
    cache_status: str = "bypass"


PRIVATE_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]


def default_config_json() -> str:
    config = {
        **DEFAULT_PROXY_CONFIG,
        "base_url": "https://api.open-meteo.com/v1/forecast",
    }
    return json.dumps(config, indent=2)


def parse_config(config_json: str) -> ProxySourceConfig:
    try:
        raw = json.loads(config_json)
    except json.JSONDecodeError as exc:
        raise ProxyError(f"Config JSON is invalid: {exc.msg}") from exc
    if not isinstance(raw, dict):
        raise ProxyError("Config JSON must be an object")
    merged = {**DEFAULT_PROXY_CONFIG, **raw}
    merged["auth"] = {**DEFAULT_PROXY_CONFIG["auth"], **raw.get("auth", {})}
    try:
        config = ProxySourceConfig.model_validate(merged)
    except Exception as exc:
        raise ProxyError("Config JSON does not match the proxy source format") from exc
    if config.method.upper() != "GET":
        raise ProxyError("Only GET proxy sources are supported")
    if config.timeout_seconds <= 0 or config.timeout_seconds > 60:
        raise ProxyError("timeout_seconds must be between 1 and 60")
    if config.max_response_bytes <= 0 or config.max_response_bytes > 10 * 1024 * 1024:
        raise ProxyError("max_response_bytes must be between 1 and 10485760")
    return config


def source_to_dict(source: ProxySourceModel) -> dict:
    return {
        "id": source.id,
        "slug": source.slug,
        "name": source.name,
        "description": source.description,
        "enabled": source.enabled,
        "public": source.public,
        "config": json.loads(source.config_json),
        "created_at": source.created_at,
        "updated_at": source.updated_at,
        "deleted_at": source.deleted_at,
    }


def validate_slug(slug: str) -> str:
    value = slug.strip()
    if not value:
        raise ProxyError("Slug is required")
    allowed = set("abcdefghijklmnopqrstuvwxyz0123456789-")
    if value != value.lower() or any(char not in allowed for char in value):
        raise ProxyError("Slug may contain only lowercase letters, numbers, and hyphens")
    return value


def create_source(slug: str, name: str, description: str | None, enabled: bool, public: bool, config: dict) -> ProxySourceModel:
    config_json = json.dumps(config, indent=2, sort_keys=True)
    parse_config(config_json)
    source = ProxySourceModel(
        id=str(uuid.uuid4()),
        slug=validate_slug(slug),
        name=name.strip(),
        description=description.strip() if description else None,
        enabled=enabled,
        public=public,
        config_json=config_json,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    if not source.name:
        raise ProxyError("Name is required")
    session = get_session_factory()()
    try:
        existing = session.scalar(select(ProxySourceModel).where(ProxySourceModel.slug == source.slug))
        if existing is not None:
            raise ProxyError("Slug is already in use", status_code=409)
        session.add(source)
        session.commit()
        session.refresh(source)
        return source
    finally:
        session.close()


def update_source(source_id: str, **changes) -> ProxySourceModel:
    session = get_session_factory()()
    try:
        source = session.scalar(select(ProxySourceModel).where(ProxySourceModel.id == source_id))
        if source is None or source.deleted_at is not None:
            raise ProxyError("Proxy source not found", status_code=404)
        if "slug" in changes and changes["slug"] is not None:
            slug = validate_slug(changes["slug"])
            existing = session.scalar(
                select(ProxySourceModel).where(
                    ProxySourceModel.slug == slug,
                    ProxySourceModel.id != source_id,
                )
            )
            if existing is not None:
                raise ProxyError("Slug is already in use", status_code=409)
            source.slug = slug
        if "name" in changes and changes["name"] is not None:
            source.name = changes["name"].strip()
            if not source.name:
                raise ProxyError("Name is required")
        if "description" in changes:
            description = changes["description"]
            source.description = description.strip() if description else None
        if "enabled" in changes and changes["enabled"] is not None:
            source.enabled = changes["enabled"]
        if "public" in changes and changes["public"] is not None:
            source.public = changes["public"]
        if "config" in changes and changes["config"] is not None:
            config_json = json.dumps(changes["config"], indent=2, sort_keys=True)
            parse_config(config_json)
            source.config_json = config_json
        source.updated_at = utc_now()
        session.commit()
        session.refresh(source)
        return source
    finally:
        session.close()


def soft_delete_source(source_id: str) -> None:
    session = get_session_factory()()
    try:
        source = session.scalar(select(ProxySourceModel).where(ProxySourceModel.id == source_id))
        if source is None or source.deleted_at is not None:
            raise ProxyError("Proxy source not found", status_code=404)
        source.deleted_at = utc_now()
        source.updated_at = utc_now()
        session.commit()
    finally:
        session.close()


def get_source_by_slug(slug: str) -> ProxySourceModel | None:
    session = get_session_factory()()
    try:
        return session.scalar(
            select(ProxySourceModel).where(
                ProxySourceModel.slug == slug,
                ProxySourceModel.enabled.is_(True),
                ProxySourceModel.deleted_at.is_(None),
            )
        )
    finally:
        session.close()


def get_source_by_id(source_id: str) -> ProxySourceModel | None:
    session = get_session_factory()()
    try:
        return session.scalar(select(ProxySourceModel).where(ProxySourceModel.id == source_id))
    finally:
        session.close()


def list_sources(include_deleted: bool = False) -> list[ProxySourceModel]:
    session = get_session_factory()()
    try:
        query = select(ProxySourceModel)
        if not include_deleted:
            query = query.where(ProxySourceModel.deleted_at.is_(None))
        return list(session.scalars(query.order_by(ProxySourceModel.created_at.desc())).all())
    finally:
        session.close()


def validate_url_safe(url: httpx.URL) -> None:
    if url.scheme not in {"http", "https"}:
        raise ProxyError("Unsupported upstream URL scheme", upstream_url=str(url))
    if not url.host:
        raise ProxyError("Upstream URL must include a host", upstream_url=str(url))
    host = url.host.strip("[]").lower()
    if host == "localhost" or host.endswith(".localhost"):
        raise ProxyError("Upstream host is not allowed", upstream_url=str(url))
    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        try:
            infos = socket.getaddrinfo(host, url.port or (443 if url.scheme == "https" else 80), type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise ProxyError("Upstream host could not be resolved", upstream_url=str(url)) from exc
        addresses = [ipaddress.ip_address(info[4][0]) for info in infos]
    for address in addresses:
        if any(address in network for network in PRIVATE_NETWORKS):
            raise ProxyError("Upstream host resolves to a private or local address", upstream_url=str(url))


def build_upstream_url(config: ProxySourceConfig, query_items: Iterable[tuple[str, str]]) -> httpx.URL:
    base_url = httpx.URL(config.base_url)
    validate_url_safe(base_url)
    incoming = list(query_items)
    allowed = set(config.allowed_query_params)
    rejected = sorted({key for key, _value in incoming if key not in allowed})
    if rejected:
        raise ProxyError(f"Query parameter is not allowed: {rejected[0]}")
    provided = {key for key, _value in incoming}
    missing = [key for key in config.required_query_params if key not in provided]
    if missing:
        raise ProxyError(f"Missing required query parameter: {missing[0]}")
    url = base_url.copy_merge_params(incoming)
    validate_url_safe(url)
    return url


def content_type_allowed(content_type: str, allowed: list[str]) -> bool:
    media_type = content_type.split(";", 1)[0].strip().lower()
    allowed_types = {item.lower() for item in allowed}
    return media_type in allowed_types


def fetch_source(source: ProxySourceModel, query_items: Iterable[tuple[str, str]]) -> ProxyResult:
    config = parse_config(source.config_json)
    url = build_upstream_url(config, query_items)
    redirects_remaining = 5
    while True:
        with httpx.Client(timeout=config.timeout_seconds) as client:
            try:
                response = client.get(url, headers={}, follow_redirects=False)
            except httpx.TimeoutException as exc:
                raise ProxyError("Upstream request timed out", status_code=504, upstream_url=str(url)) from exc
            except httpx.RequestError as exc:
                raise ProxyError("Upstream request failed", status_code=502, upstream_url=str(url)) from exc
        if response.is_redirect and config.follow_redirects:
            if redirects_remaining <= 0:
                raise ProxyError("Too many upstream redirects", status_code=502, upstream_url=str(url))
            location = response.headers.get("location")
            if not location:
                raise ProxyError("Upstream redirect did not include a location", status_code=502, upstream_url=str(url))
            url = url.join(location)
            validate_url_safe(url)
            redirects_remaining -= 1
            continue
        content_type = response.headers.get("content-type", "")
        if not content_type_allowed(content_type, config.allowed_response_content_types):
            raise ProxyError("Upstream response content type is not allowed", status_code=502, upstream_url=str(url))
        body = response.content
        if len(body) > config.max_response_bytes:
            raise ProxyError("Upstream response is too large", status_code=502, upstream_url=str(url))
        return ProxyResult(
            status_code=response.status_code,
            content_type=content_type.split(";", 1)[0].strip() or "application/octet-stream",
            body=body,
            upstream_url=str(url),
        )


def preview_body(body: bytes, content_type: str, limit: int = 4000) -> str:
    text = body[:limit].decode("utf-8", errors="replace")
    if "json" in content_type:
        try:
            return json.dumps(json.loads(text), indent=2)[:limit]
        except json.JSONDecodeError:
            return text
    return text
