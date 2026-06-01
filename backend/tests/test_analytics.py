import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.analytics.db import clear_db_cache, init_schema
from app.main import app
from app.settings import get_settings


@pytest.fixture(autouse=True)
def reset_analytics_settings():
    get_settings.cache_clear()
    clear_db_cache()
    yield
    get_settings.cache_clear()
    clear_db_cache()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "labbox.db"))
    monkeypatch.setenv("ANALYTICS_DB_PATH", str(tmp_path / "analytics.sqlite"))
    monkeypatch.setenv("ANALYTICS_DASHBOARD_TOKEN", "test-dashboard-token")
    monkeypatch.setenv("ANALYTICS_IP_HASH_PEPPER", "test-pepper")
    monkeypatch.setenv("ANALYTICS_ALLOWED_ORIGINS", "https://hmarquardt.github.io")
    get_settings.cache_clear()
    clear_db_cache()
    with TestClient(app) as c:
        yield c


def pageview_payload(
    visitor_id: str = "v_test",
    session_id: str = "s_test",
    occurred_at: str = "2026-05-30T12:34:56.000Z",
    referrer=None,
    user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
    ),
) -> dict:
    return {
        "site_id": "junkdrawer",
        "event_type": "pageview",
        "visitor_id": visitor_id,
        "session_id": session_id,
        "occurred_at": occurred_at,
        "page": {
            "url": "https://hmarquardt.github.io/junkdrawer/weather_nerd.html",
            "host": "bad.example",
            "path": "/wrong",
            "query": "",
            "title": "Weather Nerd",
        },
        "referrer": referrer,
        "utm": {"source": None, "medium": None, "campaign": None, "term": None, "content": None},
        "client": {
            "language": "en-US",
            "timezone": "America/Indiana/Indianapolis",
            "screen_width": 412,
            "screen_height": 915,
            "viewport_width": 412,
            "viewport_height": 794,
            "user_agent": user_agent,
        },
        "performance": {"load_time_ms": 842, "navigation_type": "navigate"},
    }


def dashboard_headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-dashboard-token"}


def test_schema_initialization_creates_tables(tmp_path, monkeypatch):
    db_path = tmp_path / "analytics.sqlite"
    monkeypatch.setenv("ANALYTICS_DB_PATH", str(db_path))
    get_settings.cache_clear()
    clear_db_cache()

    init_schema()

    with sqlite3.connect(db_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    assert {"sites", "visitors", "sessions", "pageviews", "events"}.issubset(tables)


def test_analytics_health_works(client, tmp_path):
    response = client.get("/api/analytics/health")

    assert response.status_code == 200
    assert response.json() == {"ok": True, "db": "ok"}
    assert (tmp_path / "analytics.sqlite").exists()


def test_valid_collect_inserts_pageview_and_upserts_visitor_and_session(client, tmp_path):
    first = client.post(
        "/api/analytics/collect",
        json=pageview_payload(),
        headers={"Origin": "https://hmarquardt.github.io"},
    )
    second = client.post(
        "/api/analytics/collect",
        json=pageview_payload(occurred_at="2026-05-30T12:40:00.000Z"),
        headers={"Origin": "https://hmarquardt.github.io"},
    )

    assert first.status_code == 200
    assert first.json() == {"ok": True}
    assert second.status_code == 200

    with sqlite3.connect(tmp_path / "analytics.sqlite") as connection:
        connection.row_factory = sqlite3.Row
        assert connection.execute("SELECT COUNT(*) FROM pageviews").fetchone()[0] == 2
        assert connection.execute("SELECT COUNT(*) FROM visitors").fetchone()[0] == 1
        session = connection.execute("SELECT pageview_count FROM sessions").fetchone()
    assert session["pageview_count"] == 2


def test_unknown_site_id_rejected(client):
    payload = pageview_payload()
    payload["site_id"] = "unknown"

    response = client.post("/api/analytics/collect", json=payload)

    assert response.status_code == 400


def test_dashboard_endpoint_rejects_missing_token(client):
    response = client.get("/api/analytics/summary?site_id=junkdrawer&from=2026-05-01&to=2026-05-30")

    assert response.status_code == 401


def test_summary_counts_pageviews_visitors_and_sessions(client):
    client.post("/api/analytics/collect", json=pageview_payload(visitor_id="v1", session_id="s1"))
    client.post("/api/analytics/collect", json=pageview_payload(visitor_id="v1", session_id="s1"))
    client.post("/api/analytics/collect", json=pageview_payload(visitor_id="v2", session_id="s2"))

    response = client.get(
        "/api/analytics/summary?site_id=junkdrawer&from=2026-05-01&to=2026-05-30",
        headers=dashboard_headers(),
    )

    assert response.status_code == 200
    assert response.json()["pageviews"] == 3
    assert response.json()["visitors"] == 2
    assert response.json()["sessions"] == 2


def test_pages_timeseries_and_recent_endpoints_work(client):
    client.post("/api/analytics/collect", json=pageview_payload(visitor_id="v1", session_id="s1"))

    pages = client.get(
        "/api/analytics/pages?site_id=junkdrawer&from=2026-05-01&to=2026-05-30",
        headers=dashboard_headers(),
    )
    timeseries = client.get(
        "/api/analytics/timeseries?site_id=junkdrawer&from=2026-05-01&to=2026-05-30",
        headers=dashboard_headers(),
    )
    recent = client.get("/api/analytics/recent?site_id=junkdrawer", headers=dashboard_headers())

    assert pages.status_code == 200
    assert pages.json()["pages"][0]["path"] == "/junkdrawer/weather_nerd.html"
    assert timeseries.status_code == 200
    assert timeseries.json()["points"][0]["pageviews"] == 1
    assert recent.status_code == 200
    assert recent.json()["visits"][0]["page_path"] == "/junkdrawer/weather_nerd.html"


def test_bot_user_agent_is_flagged(client):
    response = client.post(
        "/api/analytics/collect",
        json=pageview_payload(user_agent="curl/8.0"),
    )

    assert response.status_code == 200
    recent = client.get("/api/analytics/recent?site_id=junkdrawer", headers=dashboard_headers())
    assert recent.json()["visits"][0]["is_bot"] is True


def test_referrer_null_becomes_direct(client):
    client.post("/api/analytics/collect", json=pageview_payload(referrer=None))

    response = client.get(
        "/api/analytics/referrers?site_id=junkdrawer&from=2026-05-01&to=2026-05-30",
        headers=dashboard_headers(),
    )

    assert response.status_code == 200
    assert response.json()["referrers"][0]["domain"] == "direct"
