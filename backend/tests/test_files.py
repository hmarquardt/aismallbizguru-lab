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


@pytest.fixture
def wfr_auth_token(client, tmp_path, monkeypatch):
    from app.auth.tokens import generate_token
    from app.db.init_db import init_db
    from app.db.models import ApiTokenModel, utc_now
    from app.db.session import get_session_factory

    init_db()

    raw, token_hash = generate_token()
    session = get_session_factory()()
    try:
        token = ApiTokenModel(
            id="test-token-wfr-files",
            name="WFR File Test Token",
            token_hash=token_hash,
            scopes_json='{"wildlife-field-recorder": ["read", "write"]}',
            created_at=utc_now(),
        )
        session.add(token)
        session.commit()
    finally:
        session.close()
    return raw


def test_wfr_upload_audio_to_observation(client, wfr_auth_token, monkeypatch):
    monkeypatch.setattr("app.files.service.put_file", lambda *args, **kwargs: None)
    create_resp = client.post(
        "/api/wildlife-field-recorder/observations",
        json={
            "data": {
                "localId": "audio-test-1",
                "createdAt": "2026-05-10T20:15:00Z",
            }
        },
        headers={"Authorization": f"Bearer {wfr_auth_token}"},
    )
    assert create_resp.status_code == 201
    record_id = create_resp.json()["id"]

    response = client.post(
        f"/api/wildlife-field-recorder/observations/{record_id}/files",
        files={"file": ("observation.webm", b"fake audio data", "audio/webm")},
        headers={"Authorization": f"Bearer {wfr_auth_token}"},
    )
    assert response.status_code == 201


def test_wfr_upload_photo_to_observation(client, wfr_auth_token, monkeypatch):
    monkeypatch.setattr("app.files.service.put_file", lambda *args, **kwargs: None)
    create_resp = client.post(
        "/api/wildlife-field-recorder/observations",
        json={
            "data": {
                "localId": "photo-test-1",
                "createdAt": "2026-05-10T20:15:00Z",
            }
        },
        headers={"Authorization": f"Bearer {wfr_auth_token}"},
    )
    assert create_resp.status_code == 201
    record_id = create_resp.json()["id"]

    response = client.post(
        f"/api/wildlife-field-recorder/observations/{record_id}/files",
        files={"file": ("heron.jpg", b"fake jpeg data", "image/jpeg")},
        headers={"Authorization": f"Bearer {wfr_auth_token}"},
    )
    assert response.status_code == 201


def test_wfr_upload_geojson_to_trip(client, wfr_auth_token, monkeypatch):
    monkeypatch.setattr("app.files.service.put_file", lambda *args, **kwargs: None)
    create_resp = client.post(
        "/api/wildlife-field-recorder/trips",
        json={
            "data": {
                "localTripId": "trip-file-1",
                "title": "Trip With GeoJSON",
                "startedAt": "2026-05-10T20:00:00Z",
            }
        },
        headers={"Authorization": f"Bearer {wfr_auth_token}"},
    )
    assert create_resp.status_code == 201
    record_id = create_resp.json()["id"]

    response = client.post(
        f"/api/wildlife-field-recorder/trips/{record_id}/files",
        files={"file": ("route.geojson", b'{"type":"FeatureCollection"}', "application/geo+json")},
        headers={"Authorization": f"Bearer {wfr_auth_token}"},
    )
    assert response.status_code == 201


def test_wfr_file_upload_requires_auth(client):
    response = client.post(
        "/api/wildlife-field-recorder/observations/some-id/files",
        files={"file": ("test.webm", b"data", "audio/webm")},
    )
    assert response.status_code == 401