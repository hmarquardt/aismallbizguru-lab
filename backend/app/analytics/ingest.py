from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import UTC, datetime
from urllib.parse import urlparse

from app.analytics.bot_filter import detect_bot
from app.analytics.db import get_connection
from app.analytics.models import Site
from app.analytics.schema import AnalyticsPayload
from app.analytics.user_agent import parse_user_agent
from app.settings import get_settings

logger = logging.getLogger(__name__)


class AnalyticsError(Exception):
    pass


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: str) -> str:
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")
    except ValueError as exc:
        raise AnalyticsError("invalid event") from exc


def _short(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    if not value:
        return None
    return value[:limit]


def _hash(value: str | None, pepper: str = "") -> str | None:
    if not value:
        return None
    return hashlib.sha256(f"{pepper}:{value}".encode("utf-8")).hexdigest()


def hash_ip(ip_address: str | None) -> str | None:
    return _hash(ip_address, get_settings().analytics_ip_hash_pepper)


def _target_domain(target_url: str | None) -> str | None:
    if not target_url:
        return None
    parsed = urlparse(target_url)
    return _short(parsed.netloc.lower(), 255)


def get_site(site_id: str) -> Site | None:
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id, name, allowed_origins, is_active FROM sites WHERE id = ?",
            (site_id,),
        ).fetchone()
    if row is None:
        return None
    try:
        origins = json.loads(row["allowed_origins"])
    except json.JSONDecodeError:
        origins = []
    return Site(
        id=row["id"],
        name=row["name"],
        allowed_origins=[str(origin) for origin in origins],
        is_active=bool(row["is_active"]),
    )


def validate_origin(site: Site, origin: str | None) -> None:
    if not origin:
        return
    allowed = set(site.allowed_origins) | set(get_settings().analytics_allowed_origins)
    if origin not in allowed:
        raise AnalyticsError("invalid event")


def normalize_page(payload: AnalyticsPayload) -> dict[str, str | None]:
    parsed = urlparse(payload.page.url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise AnalyticsError("invalid event")
    path = parsed.path or "/"
    if not path.startswith("/"):
        raise AnalyticsError("invalid event")
    return {
        "url": _short(payload.page.url, 2048),
        "host": _short(parsed.netloc.lower(), 255),
        "path": _short(path, 1024),
        "query": _short(parsed.query, 1024),
        "title": _short(payload.page.title, 512),
    }


def collect(payload: AnalyticsPayload, ip_address: str | None, raw_payload: dict) -> None:
    site = get_site(payload.site_id)
    if site is None or not site.is_active:
        raise AnalyticsError("invalid event")

    page = normalize_page(payload)
    occurred_at = _parse_timestamp(payload.occurred_at)
    client = payload.client
    referrer = payload.referrer
    utm = payload.utm
    perf = payload.performance
    user_agent = client.user_agent if client else None
    ua_hash = _hash(user_agent)
    ip_hash = hash_ip(ip_address)
    ua = parse_user_agent(user_agent)
    is_bot, bot_reason = detect_bot(user_agent)
    referrer_domain = _short(referrer.domain if referrer else None, 255)
    referrer_url = _short(referrer.url if referrer else None, 2048)
    raw_json = json.dumps(raw_payload, separators=(",", ":"), sort_keys=True)[:10000]

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO visitors (
              id, site_id, first_seen_at, last_seen_at, first_path, last_path,
              user_agent_hash, ip_hash
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              last_seen_at = excluded.last_seen_at,
              last_path = excluded.last_path,
              user_agent_hash = COALESCE(visitors.user_agent_hash, excluded.user_agent_hash),
              ip_hash = COALESCE(visitors.ip_hash, excluded.ip_hash)
            """,
            (
                payload.visitor_id,
                payload.site_id,
                occurred_at,
                occurred_at,
                page["path"],
                page["path"],
                ua_hash,
                ip_hash,
            ),
        )
        is_pageview = payload.event_type == "pageview"
        connection.execute(
            """
            INSERT INTO sessions (
              id, site_id, visitor_id, started_at, last_seen_at, landing_path, exit_path,
              referrer_url, referrer_domain, utm_source, utm_medium, utm_campaign,
              pageview_count, heartbeat_count, duration_seconds, bounced
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?)
            ON CONFLICT(id) DO UPDATE SET
              last_seen_at = excluded.last_seen_at,
              exit_path = excluded.exit_path,
              pageview_count = sessions.pageview_count + ?,
              duration_seconds = MAX(0, CAST((julianday(excluded.last_seen_at) - julianday(sessions.started_at)) * 86400 AS INTEGER)),
              bounced = CASE WHEN sessions.pageview_count + ? <= 1 THEN 1 ELSE 0 END
            """,
            (
                payload.session_id,
                payload.site_id,
                payload.visitor_id,
                occurred_at,
                occurred_at,
                page["path"],
                page["path"],
                referrer_url,
                referrer_domain,
                _short(utm.source if utm else None, 255),
                _short(utm.medium if utm else None, 255),
                _short(utm.campaign if utm else None, 255),
                1 if is_pageview else 0,
                1 if is_pageview else 0,
                1 if is_pageview else 0,
                1 if is_pageview else 0,
            ),
        )
        if is_pageview:
            connection.execute(
                """
                INSERT INTO pageviews (
                  id, site_id, visitor_id, session_id, occurred_at, page_url, page_host,
                  page_path, page_query, page_title, referrer_url, referrer_domain,
                  utm_source, utm_medium, utm_campaign, utm_term, utm_content,
                  browser_name, browser_version, os_name, os_version, device_type,
                  user_agent_hash, language, timezone, screen_width, screen_height,
                  viewport_width, viewport_height, load_time_ms, navigation_type,
                  ip_hash, is_bot, bot_reason, raw_payload
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid.uuid4().hex,
                    payload.site_id,
                    payload.visitor_id,
                    payload.session_id,
                    occurred_at,
                    page["url"],
                    page["host"],
                    page["path"],
                    page["query"],
                    page["title"],
                    referrer_url,
                    referrer_domain,
                    _short(utm.source if utm else None, 255),
                    _short(utm.medium if utm else None, 255),
                    _short(utm.campaign if utm else None, 255),
                    _short(utm.term if utm else None, 255),
                    _short(utm.content if utm else None, 255),
                    ua["browser_name"],
                    ua["browser_version"],
                    ua["os_name"],
                    ua["os_version"],
                    ua["device_type"],
                    ua_hash,
                    _short(client.language if client else None, 64),
                    _short(client.timezone if client else None, 128),
                    client.screen_width if client else None,
                    client.screen_height if client else None,
                    client.viewport_width if client else None,
                    client.viewport_height if client else None,
                    perf.load_time_ms if perf else None,
                    _short(perf.navigation_type if perf else None, 64),
                    ip_hash,
                    1 if is_bot else 0,
                    bot_reason,
                    raw_json,
                ),
            )
        else:
            if not payload.event_name:
                raise AnalyticsError("invalid event")
            connection.execute(
                """
                INSERT INTO events (
                  id, site_id, visitor_id, session_id, event_type, occurred_at,
                  page_url, page_path, event_name, target_url, target_domain,
                  value_number, value_text, props_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    uuid.uuid4().hex,
                    payload.site_id,
                    payload.visitor_id,
                    payload.session_id,
                    _short(payload.event_type, 64),
                    occurred_at,
                    page["url"],
                    page["path"],
                    _short(payload.event_name, 255),
                    _short(payload.target_url, 2048),
                    _target_domain(payload.target_url),
                    payload.value_number,
                    _short(payload.value_text, 1024),
                    json.dumps(payload.props or {}, separators=(",", ":"), sort_keys=True)[:10000],
                ),
            )
    logger.info("analytics event collected site_id=%s event_type=%s", payload.site_id, payload.event_type)

