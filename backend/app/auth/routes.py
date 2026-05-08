import json
import uuid
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from pydantic import BaseModel

from app.auth.password import verify_password
from app.auth.tokens import generate_token, masked_token
from app.db.models import ApiTokenModel, utc_now
from app.db.session import get_session_factory
from app.settings import get_settings


router = APIRouter(prefix="/api/admin", tags=["admin-api"])


def require_admin(session: Annotated[str | None, Cookie()] = None) -> None:
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    settings = get_settings()
    if session != settings.admin_session_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")


class TokenCreate(BaseModel):
    name: str
    scopes: dict[str, list[str]] = {}


class TokenCreated(BaseModel):
    id: str
    name: str
    token: str
    scopes: dict[str, list[str]]
    created_at: str


class TokenOut(BaseModel):
    id: str
    name: str
    masked_token: str
    scopes: dict[str, list[str]]
    created_at: str
    expires_at: str | None
    revoked_at: str | None

    @classmethod
    def from_model(cls, model: ApiTokenModel) -> "TokenOut":
        scopes: dict[str, list[str]] = json.loads(model.scopes_json) if model.scopes_json else {}
        return cls(
            id=model.id,
            name=model.name,
            masked_token=masked_token(model.token_hash),
            scopes=scopes,
            created_at=model.created_at,
            expires_at=model.expires_at,
            revoked_at=model.revoked_at,
        )


@router.post("/tokens", status_code=status.HTTP_201_CREATED)
def create_token(
    body: TokenCreate,
    _: Annotated[None, Depends(require_admin)],
) -> TokenCreated:
    raw, token_hash = generate_token()
    token_id = str(uuid.uuid4())

    session = get_session_factory()()
    try:
        model = ApiTokenModel(
            id=token_id,
            name=body.name,
            token_hash=token_hash,
            scopes_json=json.dumps(body.scopes),
            created_at=utc_now(),
        )
        session.add(model)
        session.commit()
        session.refresh(model)
    finally:
        session.close()

    return TokenCreated(
        id=model.id,
        name=model.name,
        token=raw,
        scopes=body.scopes,
        created_at=model.created_at,
    )


@router.get("/tokens")
def list_tokens(
    _: Annotated[None, Depends(require_admin)],
) -> list[TokenOut]:
    from sqlalchemy import select

    session = get_session_factory()()
    try:
        tokens = session.scalars(
            select(ApiTokenModel).order_by(ApiTokenModel.created_at.desc())
        ).all()
        return [TokenOut.from_model(t) for t in tokens]
    finally:
        session.close()


@router.post("/tokens/{token_id}/revoke")
def revoke_token(
    token_id: str,
    _: Annotated[None, Depends(require_admin)],
) -> dict[str, str]:
    from sqlalchemy import select

    session = get_session_factory()()
    try:
        token = session.scalar(select(ApiTokenModel).where(ApiTokenModel.id == token_id))
        if not token:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Token not found")
        token.revoked_at = utc_now()
        session.commit()
    finally:
        session.close()

    return {"status": "revoked"}


class LoginRequest(BaseModel):
    password: str


@router.post("/login")
def login(response: Response, body: LoginRequest) -> dict[str, str]:
    settings = get_settings()
    if not settings.admin_session_secret:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Admin session not configured")
    if not settings.admin_password_hash:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Admin password not configured")

    if not verify_password(body.password, settings.admin_password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password")

    response.set_cookie(
        key="session",
        value=settings.admin_session_secret,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=86400 * 7,
    )
    return {"status": "logged in"}


@router.post("/logout")
def logout(response: Response, _: Annotated[None, Depends(require_admin)]) -> dict[str, str]:
    response.delete_cookie(key="session")
    return {"status": "logged out"}
