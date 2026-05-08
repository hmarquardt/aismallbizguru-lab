from fastapi.testclient import TestClient

from app.config.loader import clear_registry_cache
from app.db.session import clear_engine_cache
from app.main import create_app
from app.settings import get_settings


def test_configured_cors_origin_gets_preflight_headers(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "labbox.db"))
    monkeypatch.setenv("CORS_ALLOW_ORIGINS", "https://example.github.io")
    get_settings.cache_clear()
    clear_registry_cache()
    clear_engine_cache()

    with TestClient(create_app()) as client:
        response = client.options(
            "/api/apps",
            headers={
                "Origin": "https://example.github.io",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://example.github.io"
