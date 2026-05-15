import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.auth.tokens import generate_token
from app.db.init_db import init_db
from app.db.models import ApiTokenModel, ProxySourceModel, utc_now
from app.db.session import clear_engine_cache, get_session_factory
from app.main import app
from app.proxy.service import create_source
from app.settings import get_settings


@pytest.fixture(autouse=True)
def reset_settings():
    get_settings.cache_clear()
    clear_engine_cache()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "labbox.db"))
    get_settings.cache_clear()
    clear_engine_cache()
    c = TestClient(app)
    c.get("/api/health")
    return c


@pytest.fixture
def auth_token(client):
    init_db()
    raw, token_hash = generate_token()
    session = get_session_factory()()
    try:
        session.add(
            ApiTokenModel(
                id="proxy-token-1",
                name="Proxy Token",
                token_hash=token_hash,
                scopes_json='{"weather-app": ["read"]}',
                created_at=utc_now(),
            )
        )
        session.commit()
    finally:
        session.close()
    return raw


def proxy_config(**overrides):
    config = {
        "base_url": "https://example.com/api",
        "method": "GET",
        "allowed_query_params": ["q", "required"],
        "required_query_params": [],
        "allowed_response_content_types": ["application/json"],
        "timeout_seconds": 10,
        "max_response_bytes": 1024,
        "follow_redirects": False,
        "auth": {"mode": "public", "scope_app": None, "required_scope": "read"},
    }
    config.update(overrides)
    return config


def add_source(slug="test-source", public=True, enabled=True, config=None):
    return create_source(
        slug,
        "Test Source",
        None,
        enabled,
        public,
        config or proxy_config(),
    )


class StubClient:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url, headers=None, follow_redirects=False):
        request = httpx.Request("GET", url)
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            content=b'{"ok": true}',
            request=request,
        )


def stub_http(monkeypatch, client_class=StubClient):
    monkeypatch.setattr("app.proxy.service.validate_url_safe", lambda _url: None)
    monkeypatch.setattr("app.proxy.service.httpx.Client", client_class)


def test_admin_api_create_proxy_source(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "labbox.db"))
    monkeypatch.setenv("ADMIN_SESSION_SECRET", "test-session")
    get_settings.cache_clear()
    clear_engine_cache()
    with TestClient(app) as api_client:
        api_client.cookies.set("session", "test-session")
        response = api_client.post(
            "/api/admin/proxy-sources",
            json={
                "slug": "open-meteo",
                "name": "Open-Meteo",
                "description": "Weather API",
                "enabled": True,
                "public": True,
                "config": proxy_config(),
            },
        )
    assert response.status_code == 201
    assert response.json()["slug"] == "open-meteo"


def test_public_source_can_be_called_without_token(client, monkeypatch):
    init_db()
    add_source()
    stub_http(monkeypatch)

    response = client.get("/api/proxy/test-source?q=weather")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert response.headers["x-labbox-proxy-source"] == "test-source"


def test_private_source_requires_token(client, monkeypatch):
    init_db()
    add_source(public=False, config=proxy_config(auth={"mode": "private", "scope_app": None, "required_scope": "read"}))
    stub_http(monkeypatch)

    response = client.get("/api/proxy/test-source?q=weather")

    assert response.status_code == 401


def test_private_source_accepts_valid_token(client, auth_token, monkeypatch):
    init_db()
    add_source(public=False, config=proxy_config(auth={"mode": "private", "scope_app": None, "required_scope": "read"}))
    stub_http(monkeypatch)

    response = client.get("/api/proxy/test-source?q=weather", headers={"Authorization": f"Bearer {auth_token}"})

    assert response.status_code == 200


def test_unknown_slug_returns_404(client):
    init_db()

    response = client.get("/api/proxy/missing")

    assert response.status_code == 404


def test_disabled_source_returns_404(client):
    init_db()
    add_source(enabled=False)

    response = client.get("/api/proxy/test-source")

    assert response.status_code == 404


def test_disallowed_query_param_rejected(client, monkeypatch):
    init_db()
    add_source()
    stub_http(monkeypatch)

    response = client.get("/api/proxy/test-source?bad=1")

    assert response.status_code == 400
    assert "not allowed" in response.json()["detail"]


def test_missing_required_query_param_rejected(client, monkeypatch):
    init_db()
    add_source(config=proxy_config(required_query_params=["required"]))
    stub_http(monkeypatch)

    response = client.get("/api/proxy/test-source?q=weather")

    assert response.status_code == 400
    assert "Missing required" in response.json()["detail"]


def test_unsafe_localhost_base_url_rejected(client):
    init_db()
    add_source(config=proxy_config(base_url="http://localhost:8000/data"))

    response = client.get("/api/proxy/test-source?q=weather")

    assert response.status_code == 400
    assert "not allowed" in response.json()["detail"]


def test_unsupported_scheme_rejected(client):
    init_db()
    session = get_session_factory()()
    try:
        session.add(
            ProxySourceModel(
                id="unsafe-scheme-source",
                slug="unsafe-scheme",
                name="Unsafe Scheme",
                enabled=True,
                public=True,
                config_json=json.dumps(proxy_config(base_url="ftp://example.com/data")),
                created_at=utc_now(),
                updated_at=utc_now(),
            )
        )
        session.commit()
    finally:
        session.close()

    response = client.get("/api/proxy/unsafe-scheme?q=weather")

    assert response.status_code == 400
    assert "Unsupported" in response.json()["detail"]


def test_oversized_response_rejected(client, monkeypatch):
    class LargeClient(StubClient):
        def get(self, url, headers=None, follow_redirects=False):
            request = httpx.Request("GET", url)
            return httpx.Response(
                200,
                headers={"content-type": "application/json"},
                content=b'{"data":"' + b"x" * 32 + b'"}',
                request=request,
            )

    init_db()
    add_source(config=proxy_config(max_response_bytes=10))
    stub_http(monkeypatch, LargeClient)

    response = client.get("/api/proxy/test-source?q=weather")

    assert response.status_code == 502
    assert "too large" in response.json()["detail"]


def test_content_type_rejected(client, monkeypatch):
    class HtmlClient(StubClient):
        def get(self, url, headers=None, follow_redirects=False):
            request = httpx.Request("GET", url)
            return httpx.Response(
                200,
                headers={"content-type": "text/html"},
                content=b"<html></html>",
                request=request,
            )

    init_db()
    add_source()
    stub_http(monkeypatch, HtmlClient)

    response = client.get("/api/proxy/test-source?q=weather")

    assert response.status_code == 502
    assert "content type" in response.json()["detail"]
