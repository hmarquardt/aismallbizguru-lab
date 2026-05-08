import pytest
from fastapi.testclient import TestClient

from app.auth.tokens import generate_token
from app.config.loader import clear_registry_cache
from app.db.models import ApiTokenModel, utc_now
from app.db.session import clear_engine_cache, get_session_factory
from app.main import app
from app.settings import get_settings


@pytest.fixture(autouse=True)
def reset_settings():
    get_settings.cache_clear()
    clear_registry_cache()
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
            id="test-token-1",
            name="Test Token",
            token_hash=token_hash,
            scopes_json='{"junk-drawer": ["read", "write"]}',
            created_at=utc_now(),
        )
        session.add(token)
        session.commit()
    finally:
        session.close()

    return raw


def test_create_record(client, auth_token):
    response = client.post(
        "/api/junk-drawer/notes",
        json={"data": {"title": "My Note", "body": "Hello world"}},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 201
    json = response.json()
    assert json["app_id"] == "junk-drawer"
    assert json["resource"] == "notes"
    assert json["data"]["title"] == "My Note"


def test_list_records(client, auth_token):
    client.post(
        "/api/junk-drawer/notes",
        json={"data": {"title": "Note 1"}},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    client.post(
        "/api/junk-drawer/notes",
        json={"data": {"title": "Note 2"}},
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    response = client.get(
        "/api/junk-drawer/notes",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    json = response.json()
    assert json["total"] == 2
    assert len(json["records"]) == 2


def test_update_record(client, auth_token):
    create_resp = client.post(
        "/api/junk-drawer/notes",
        json={"data": {"title": "Original"}},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    record_id = create_resp.json()["id"]

    response = client.patch(
        f"/api/junk-drawer/notes/{record_id}",
        json={"data": {"title": "Updated"}},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["title"] == "Updated"


def test_soft_delete(client, auth_token):
    create_resp = client.post(
        "/api/junk-drawer/notes",
        json={"data": {"title": "To Delete"}},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    record_id = create_resp.json()["id"]

    response = client.delete(
        f"/api/junk-drawer/notes/{record_id}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 200

    list_resp = client.get(
        "/api/junk-drawer/notes",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert list_resp.json()["total"] == 0


def test_unknown_resource(client, auth_token):
    response = client.get(
        "/api/junk-drawer/nonexistent",
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 400


def test_unauthorized_write(client):
    response = client.post(
        "/api/junk-drawer/notes",
        json={"data": {"title": "Should fail"}},
    )
    assert response.status_code == 401


def test_unauthorized_read(client):
    response = client.get("/api/junk-drawer/notes")
    assert response.status_code == 401


def test_public_read_resource_allows_unauthenticated_list_and_get(tmp_path, monkeypatch):
    config_path = tmp_path / "apps.yaml"
    config_path.write_text(
        """
apps:
  public-site:
    title: Public Site
    auth:
      default_read: public
      default_write: token
    resources:
      posts:
        label: Posts
        fields:
          title:
            type: string
            required: true
""",
    )
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "labbox.db"))
    monkeypatch.setenv("APP_CONFIG_PATH", str(config_path))
    get_settings.cache_clear()
    clear_registry_cache()
    clear_engine_cache()

    from app.db.init_db import init_db
    from app.records.service import create_record

    init_db()
    record = create_record("public-site", "posts", {"title": "Published"})

    with TestClient(app) as public_client:
        list_response = public_client.get("/api/public-site/posts")
        get_response = public_client.get(f"/api/public-site/posts/{record.id}")

    assert list_response.status_code == 200
    assert list_response.json()["records"][0]["data"]["title"] == "Published"
    assert get_response.status_code == 200
    assert get_response.json()["data"]["title"] == "Published"


def test_public_read_does_not_allow_unauthenticated_write(tmp_path, monkeypatch):
    config_path = tmp_path / "apps.yaml"
    config_path.write_text(
        """
apps:
  public-site:
    title: Public Site
    auth:
      default_read: public
      default_write: token
    resources:
      posts:
        label: Posts
        fields:
          title:
            type: string
            required: true
""",
    )
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "labbox.db"))
    monkeypatch.setenv("APP_CONFIG_PATH", str(config_path))
    get_settings.cache_clear()
    clear_registry_cache()
    clear_engine_cache()

    with TestClient(app) as public_client:
        response = public_client.post("/api/public-site/posts", json={"data": {"title": "Nope"}})

    assert response.status_code == 401
