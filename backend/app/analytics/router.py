from __future__ import annotations

import json
import logging
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import ValidationError

from app.analytics import queries
from app.analytics.db import check_db
from app.analytics.ingest import AnalyticsError, collect, get_site, hash_ip, validate_origin
from app.analytics.rate_limit import limiter
from app.analytics.schema import AnalyticsPayload
from app.settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])
MAX_BODY_BYTES = 32 * 1024


def require_dashboard_token(authorization: Annotated[str | None, Header()] = None) -> None:
    expected = get_settings().analytics_dashboard_token
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing bearer token")
    if authorization[7:] != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing bearer token")


def require_site(site_id: str) -> None:
    site = get_site(site_id)
    if site is None or not site.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown site")


def _client_ip(request: Request) -> str | None:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    return request.client.host if request.client else None


@router.get("/health")
def health() -> dict[str, bool | str]:
    return {"ok": True, "db": "ok" if check_db() else "error"}


@router.post("/collect")
async def collect_event(request: Request) -> dict[str, bool]:
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_BODY_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Request too large")

    body = await request.body()
    if len(body) > MAX_BODY_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="Request too large")

    try:
        raw_payload = json.loads(body)
        payload = AnalyticsPayload.model_validate(raw_payload)
        site = get_site(payload.site_id)
        if site is None or not site.is_active:
            raise AnalyticsError("invalid event")
        validate_origin(site, request.headers.get("origin"))
        ip_hash = hash_ip(_client_ip(request)) or "unknown"
        if not limiter.allow(f"{payload.site_id}:{ip_hash}"):
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests")
        collect(payload, _client_ip(request), raw_payload)
    except HTTPException:
        raise
    except (AnalyticsError, ValidationError, json.JSONDecodeError) as exc:
        logger.info("analytics collect rejected: %s", exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid analytics event")
    except Exception:
        logger.exception("analytics collect failed")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid analytics event")
    return {"ok": True}


@router.get("/summary", dependencies=[Depends(require_dashboard_token)])
def get_summary(site_id: str, from_: Annotated[date, Query(alias="from")], to: date) -> dict:
    require_site(site_id)
    return queries.summary(site_id, from_, to)


@router.get("/timeseries", dependencies=[Depends(require_dashboard_token)])
def get_timeseries(
    site_id: str,
    from_: Annotated[date, Query(alias="from")],
    to: date,
    bucket: Annotated[str, Query(pattern="^(day|hour)$")] = "day",
) -> dict:
    require_site(site_id)
    return queries.timeseries(site_id, from_, to, bucket)


@router.get("/pages", dependencies=[Depends(require_dashboard_token)])
def get_pages(
    site_id: str,
    from_: Annotated[date, Query(alias="from")],
    to: date,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
) -> dict:
    require_site(site_id)
    return queries.pages(site_id, from_, to, limit)


@router.get("/referrers", dependencies=[Depends(require_dashboard_token)])
def get_referrers(
    site_id: str,
    from_: Annotated[date, Query(alias="from")],
    to: date,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
) -> dict:
    require_site(site_id)
    return queries.referrers(site_id, from_, to, limit)


@router.get("/recent", dependencies=[Depends(require_dashboard_token)])
def get_recent(
    site_id: str,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> dict:
    require_site(site_id)
    return queries.recent(site_id, limit)

