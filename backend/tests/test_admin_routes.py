from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.init_db import init_db
from app.db.models import RecordModel
from app.db.session import clear_engine_cache, get_session_factory
from app.main import app
from app.records.service import create_record
from app.settings import get_settings


def test_admin_login_page_imports_and_renders(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "labbox.db"))
    get_settings.cache_clear()
    clear_engine_cache()

    with TestClient(app) as client:
        response = client.get("/admin/login")

    assert response.status_code == 200
    assert "LabBox Admin" in response.text


def test_json_admin_login_lives_under_api_admin(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "labbox.db"))
    monkeypatch.delenv("ADMIN_SESSION_SECRET", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD_HASH", raising=False)
    get_settings.cache_clear()
    clear_engine_cache()

    with TestClient(app) as client:
        response = client.post("/api/admin/login", json={"password": "bad"})

    assert response.status_code == 500
    assert response.json()["detail"] == "Admin session not configured"


def test_backup_api_route_lives_under_api_admin(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "labbox.db"))
    get_settings.cache_clear()
    clear_engine_cache()

    with TestClient(app) as client:
        response = client.get("/api/admin/backups")

    assert response.status_code == 401


def test_backup_api_rejects_invalid_admin_cookie(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "labbox.db"))
    monkeypatch.setenv("ADMIN_SESSION_SECRET", "real-session")
    get_settings.cache_clear()
    clear_engine_cache()

    with TestClient(app) as client:
        client.cookies.set("session", "wrong-session")
        response = client.get("/api/admin/backups")

    assert response.status_code == 401


def test_admin_resource_browser_links_from_apps(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "labbox.db"))
    monkeypatch.setenv("ADMIN_SESSION_SECRET", "test-session")
    get_settings.cache_clear()
    clear_engine_cache()

    with TestClient(app) as client:
        client.cookies.set("session", "test-session")
        response = client.get("/admin/apps")

    assert response.status_code == 200
    assert "/admin/apps/junk-drawer/notes" in response.text


def test_admin_can_create_and_edit_record(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "labbox.db"))
    monkeypatch.setenv("ADMIN_SESSION_SECRET", "test-session")
    get_settings.cache_clear()
    clear_engine_cache()

    with TestClient(app) as client:
        init_db()
        client.cookies.set("session", "test-session")
        create_response = client.post(
            "/admin/apps/junk-drawer/notes/new",
            data={"title": "Admin Note", "body": "Created in admin", "tags": '["admin"]', "pinned": "on"},
            follow_redirects=False,
        )

        assert create_response.status_code == 303
        detail_location = create_response.headers["Location"]
        detail_response = client.get(detail_location)
        assert detail_response.status_code == 200
        assert "Admin Note" in detail_response.text

        record_id = detail_location.rsplit("/", 1)[-1]
        edit_response = client.post(
            f"/admin/records/{record_id}",
            data={"title": "Updated Note", "body": "Edited", "tags": '["edited"]'},
            follow_redirects=False,
        )

    assert edit_response.status_code == 303

    session = get_session_factory()()
    try:
        record = session.scalar(select(RecordModel).where(RecordModel.id == record_id))
        assert record is not None
        assert "Updated Note" in record.data_json
        assert '"pinned": false' in record.data_json
    finally:
        session.close()


def test_admin_can_soft_delete_record(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "labbox.db"))
    monkeypatch.setenv("ADMIN_SESSION_SECRET", "test-session")
    get_settings.cache_clear()
    clear_engine_cache()

    with TestClient(app) as client:
        init_db()
        record = create_record("junk-drawer", "notes", {"title": "Delete Me"})
        client.cookies.set("session", "test-session")
        response = client.post(f"/admin/records/{record.id}/delete", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["Location"] == "/admin/apps/junk-drawer/notes"

    session = get_session_factory()()
    try:
        deleted = session.scalar(select(RecordModel).where(RecordModel.id == record.id))
        assert deleted is not None
        assert deleted.deleted_at is not None
    finally:
        session.close()
