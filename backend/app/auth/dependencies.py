from typing import Annotated

from fastapi import Cookie, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.tokens import hash_token
from app.config.loader import get_registry
from app.db.models import ApiTokenModel
from app.db.session import get_session_factory
from app.settings import get_settings


def _extract_bearer(value: str | None) -> str | None:
    if not value:
        return None
    if not value.startswith("Bearer "):
        return None
    return value[7:]


def get_optional_token(
    authorization: Annotated[str | None, Header()] = None,
) -> ApiTokenModel | None:
    raw = _extract_bearer(authorization)
    if not raw:
        return None

    token_hash = hash_token(raw)
    session: Session = get_session_factory()()
    try:
        return session.scalar(
            select(ApiTokenModel).where(
                ApiTokenModel.token_hash == token_hash,
                ApiTokenModel.revoked_at.is_(None),
            )
        )
    finally:
        session.close()


def get_required_token(
    token: Annotated[ApiTokenModel | None, Depends(get_optional_token)],
) -> ApiTokenModel:
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing bearer token",
        )
    return token


def check_scope(token: ApiTokenModel, app_id: str, required_level: str = "write") -> None:
    import json

    if not token.scopes_json:
        return

    scopes: dict[str, list[str]] = json.loads(token.scopes_json)
    app_scopes = scopes.get(app_id, [])
    if "*" in app_scopes or required_level in app_scopes:
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=f"Insufficient scope for {app_id}",
    )


def check_read_access(token: ApiTokenModel | None, app_id: str) -> None:
    app = get_registry().get_app(app_id)
    if app is not None and app.auth.default_read == "public":
        return
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing bearer token",
        )
    check_scope(token, app_id, "read")


def get_admin_session(
    session: Annotated[str | None, Cookie()] = None,
) -> str | None:
    if not session:
        return None
    settings = get_settings()
    if not settings.admin_session_secret:
        return None
    if session != settings.admin_session_secret:
        return None
    return session
