from fastapi.testclient import TestClient

from app.config.loader import clear_registry_cache
from app.settings import get_settings
from app.main import app


def test_list_apps() -> None:
    get_settings.cache_clear()
    clear_registry_cache()
    client = TestClient(app)

    response = client.get("/api/apps")

    assert response.status_code == 200
    assert "junk-drawer" in response.json()["apps"]


def test_get_unknown_app_returns_404() -> None:
    clear_registry_cache()
    client = TestClient(app)

    response = client.get("/api/apps/unknown")

    assert response.status_code == 404
