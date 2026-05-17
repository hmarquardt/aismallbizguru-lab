from fastapi.testclient import TestClient

from app.db.session import clear_engine_cache
from app.main import app
from app.settings import get_settings


def test_health_endpoint(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "labbox.db"))
    monkeypatch.setenv("BASE_URL", "https://lab.aismallbizguru.com")
    monkeypatch.setenv("STORAGE_HEALTH_ENABLED", "false")
    get_settings.cache_clear()
    clear_engine_cache()
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "version": "0.2.1",
        "host": "lab.aismallbizguru.com",
        "db": "ok",
        "storage": "unknown",
    }
