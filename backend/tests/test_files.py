import pytest
from fastapi.testclient import TestClient

from app.auth.tokens import generate_token
from app.db.models import ApiTokenModel, utc_now
from app.db.session import clear_engine_cache, get_session_factory
from app.main import app
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
def auth_token(client, tmp_path, monkeypatch):
    from app.db.init_db import init_db
    init_db()

    raw, token_hash = generate_token()
    session = get_session_factory()()
    try:
        token = ApiTokenModel(
            id="test-token-file",
            name="File Test Token",
            token_hash=token_hash,
            scopes_json='{"junk-drawer": ["read", "write"]}',
            created_at=utc_now(),
        )
        session.add(token)
        session.commit()
    finally:
        session.close()
    return raw


def test_upload_requires_auth(client):
    response = client.post(
        "/api/junk-drawer/notes/some-record/files",
        files={"file": ("test.txt", b"hello world", "text/plain")},
    )
    assert response.status_code == 401


def test_upload_to_unknown_resource(client, auth_token):
    response = client.post(
        "/api/junk-drawer/nonexistent/some-record/files",
        files={"file": ("test.txt", b"hello world", "text/plain")},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 400


def test_delete_file_not_found(client, auth_token):
    response = client.delete(
        "/api/files/nonexistent-id",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 404


def test_download_file_not_found(client, auth_token):
    response = client.get(
        "/api/files/nonexistent-id",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 404


def test_list_files_for_unknown_resource(client, auth_token):
    response = client.get(
        "/api/junk-drawer/nonexistent/some-record/files",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 400