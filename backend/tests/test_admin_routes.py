from fastapi.testclient import TestClient

from app.db.session import clear_engine_cache
from app.main import app
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
