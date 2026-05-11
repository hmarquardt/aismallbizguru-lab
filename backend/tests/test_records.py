import pytest
from fastapi.testclient import TestClient

from app.auth.tokens import generate_token
from app.config.loader import clear_registry_cache
from app.db.models import ApiTokenModel, FileModel, utc_now
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
    assert json["created_by_token_id"] == "test-token-1"


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


def test_record_list_includes_attached_file_urls(client, auth_token):
    create_resp = client.post(
        "/api/junk-drawer/notes",
        json={"data": {"title": "Photo Note"}},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    record_id = create_resp.json()["id"]

    session = get_session_factory()()
    try:
        session.add(
            FileModel(
                id="test-file-1",
                app_id="junk-drawer",
                resource="notes",
                record_id=record_id,
                bucket="labbox-assets",
                object_key=f"junk-drawer/{record_id}/test-photo.webp",
                filename="test-photo.webp",
                content_type="image/webp",
                size_bytes=12,
                checksum="abc123",
                created_at=utc_now(),
            )
        )
        session.commit()
    finally:
        session.close()

    response = client.get(
        "/api/junk-drawer/notes",
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    assert response.status_code == 200
    record = response.json()["records"][0]
    assert record["files"][0]["url"] == "https://lab.aismallbizguru.com/api/files/test-file-1"
    assert record["files"][0]["download_url"] == "https://lab.aismallbizguru.com/api/files/test-file-1"
    assert record["data"]["photo_url"] == "https://lab.aismallbizguru.com/api/files/test-file-1"


def test_record_photo_url_is_not_overwritten(client, auth_token):
    create_resp = client.post(
        "/api/junk-drawer/notes",
        json={"data": {"title": "Photo Note", "photo_url": "https://example.com/photo.jpg"}},
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    record_id = create_resp.json()["id"]

    session = get_session_factory()()
    try:
        session.add(
            FileModel(
                id="test-file-2",
                app_id="junk-drawer",
                resource="notes",
                record_id=record_id,
                bucket="labbox-assets",
                object_key=f"junk-drawer/{record_id}/test-photo.webp",
                filename="test-photo.webp",
                content_type="image/webp",
                size_bytes=12,
                checksum="abc123",
                created_at=utc_now(),
            )
        )
        session.commit()
    finally:
        session.close()

    response = client.get(
        f"/api/junk-drawer/notes/{record_id}",
        headers={"Authorization": f"Bearer {auth_token}"},
    )

    assert response.status_code == 200
    assert response.json()["data"]["photo_url"] == "https://example.com/photo.jpg"


@pytest.fixture
def wfr_auth_token(client, tmp_path, monkeypatch):
    from app.db.init_db import init_db
    init_db()

    raw, token_hash = generate_token()
    session = get_session_factory()()
    try:
        token = ApiTokenModel(
            id="test-token-wfr",
            name="WFR Test Token",
            token_hash=token_hash,
            scopes_json='{"wildlife-field-recorder": ["read", "write"]}',
            created_at=utc_now(),
        )
        session.add(token)
        session.commit()
    finally:
        session.close()

    return raw


def test_create_wildlife_observation(client, wfr_auth_token):
    response = client.post(
        "/api/wildlife-field-recorder/observations",
        json={
            "data": {
                "localId": "local-demo-1",
                "createdAt": "2026-05-10T20:15:00Z",
                "latitude": 38.3553,
                "longitude": -87.5675,
                "gpsStatus": "ok",
                "transcript": "Great blue heron near the lake.",
                "subjectCommonName": "Great Blue Heron",
                "category": "bird",
                "tags": ["lake", "heron"],
                "summary": "Great blue heron observed.",
                "photoCount": 0,
            }
        },
        headers={"Authorization": f"Bearer {wfr_auth_token}"},
    )
    assert response.status_code == 201
    json = response.json()
    assert json["app_id"] == "wildlife-field-recorder"
    assert json["resource"] == "observations"
    assert json["data"]["localId"] == "local-demo-1"
    assert json["data"]["latitude"] == 38.3553


def test_list_wildlife_observations(client, wfr_auth_token):
    client.post(
        "/api/wildlife-field-recorder/observations",
        json={
            "data": {
                "localId": "obs-1",
                "createdAt": "2026-05-10T20:15:00Z",
                "latitude": 38.3553,
                "longitude": -87.5675,
            }
        },
        headers={"Authorization": f"Bearer {wfr_auth_token}"},
    )
    client.post(
        "/api/wildlife-field-recorder/observations",
        json={
            "data": {
                "localId": "obs-2",
                "createdAt": "2026-05-10T21:00:00Z",
                "latitude": 38.3600,
                "longitude": -87.5700,
            }
        },
        headers={"Authorization": f"Bearer {wfr_auth_token}"},
    )

    response = client.get(
        "/api/wildlife-field-recorder/observations",
        headers={"Authorization": f"Bearer {wfr_auth_token}"},
    )
    assert response.status_code == 200
    json = response.json()
    assert json["total"] == 2


def test_wildlife_observation_requires_token(client):
    response = client.post(
        "/api/wildlife-field-recorder/observations",
        json={
            "data": {
                "localId": "unauthorized",
                "createdAt": "2026-05-10T20:15:00Z",
            }
        },
    )
    assert response.status_code == 401


def test_create_wildlife_trip(client, wfr_auth_token):
    response = client.post(
        "/api/wildlife-field-recorder/trips",
        json={
            "data": {
                "localTripId": "trip-demo-1",
                "title": "Evening Wildlife Drive",
                "startedAt": "2026-05-10T20:00:00Z",
                "endedAt": "2026-05-10T22:15:00Z",
                "observationLocalIds": ["local-demo-1", "local-demo-2"],
                "observationCount": 2,
                "categories": ["bird", "reptile"],
                "centerLatitude": 38.3553,
                "centerLongitude": -87.5675,
                "totalDistanceEstimateMiles": 3.4,
                "tripSummary": "Evening drive with lakeside bird activity.",
                "routeGeoJson": {
                    "type": "FeatureCollection",
                    "features": [],
                },
            }
        },
        headers={"Authorization": f"Bearer {wfr_auth_token}"},
    )
    assert response.status_code == 201
    json = response.json()
    assert json["app_id"] == "wildlife-field-recorder"
    assert json["resource"] == "trips"
    assert json["data"]["title"] == "Evening Wildlife Drive"
    assert json["data"]["routeGeoJson"]["type"] == "FeatureCollection"


def test_create_wildlife_trip_from_observations(client, wfr_auth_token):
    for payload in (
        {
            "localId": "cluster-obs-1",
            "createdAt": "2026-05-10T20:15:00Z",
            "latitude": 38.3553,
            "longitude": -87.5675,
            "weatherCondition": "cloudy",
            "temperatureF": 71.0,
            "barometricPressureHpa": 1012.1,
            "subjectCommonName": "Great Blue Heron",
            "category": "bird",
            "habitat": "lake",
        },
        {
            "localId": "cluster-obs-2",
            "createdAt": "2026-05-10T20:42:00Z",
            "latitude": 38.3561,
            "longitude": -87.5682,
            "weatherCondition": "cloudy",
            "temperatureF": 73.0,
            "barometricPressureHpa": 1011.9,
            "subjectCommonName": "Bullfrog",
            "category": "amphibian",
            "habitat": "wetland",
        },
    ):
        response = client.post(
            "/api/wildlife-field-recorder/observations",
            json={"data": payload},
            headers={"Authorization": f"Bearer {wfr_auth_token}"},
        )
        assert response.status_code == 201

    response = client.post(
        "/api/wildlife-field-recorder/trips/from-observations",
        json={
            "title": "Cloudy Lake Walk",
            "observation_local_ids": ["cluster-obs-1", "cluster-obs-2"],
        },
        headers={"Authorization": f"Bearer {wfr_auth_token}"},
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert data["title"] == "Cloudy Lake Walk"
    assert data["startedAt"] == "2026-05-10T20:15:00Z"
    assert data["endedAt"] == "2026-05-10T20:42:00Z"
    assert data["observationLocalIds"] == ["cluster-obs-1", "cluster-obs-2"]
    assert data["observationCount"] == 2
    assert data["categories"] == ["amphibian", "bird"]
    assert data["dominantWeatherCondition"] == "cloudy"
    assert data["minTemperatureF"] == 71.0
    assert data["maxTemperatureF"] == 73.0
    assert data["avgTemperatureF"] == 72.0
    assert data["avgBarometricPressureHpa"] == 1012.0
    assert data["centerLatitude"] == pytest.approx(38.3557)
    assert data["centerLongitude"] == pytest.approx(-87.56785)
    assert data["boundingBox"] == {
        "minLatitude": 38.3553,
        "maxLatitude": 38.3561,
        "minLongitude": -87.5682,
        "maxLongitude": -87.5675,
    }
    assert data["routeGeoJson"]["features"][0]["geometry"]["coordinates"] == [
        [-87.5675, 38.3553],
        [-87.5682, 38.3561],
    ]
    assert data["reviewStatus"] == "needs-review"


def test_create_wildlife_trip_from_observations_requires_selection(client, wfr_auth_token):
    response = client.post(
        "/api/wildlife-field-recorder/trips/from-observations",
        json={"title": "No Observations"},
        headers={"Authorization": f"Bearer {wfr_auth_token}"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "At least one observation is required"


def test_list_wildlife_trips(client, wfr_auth_token):
    client.post(
        "/api/wildlife-field-recorder/trips",
        json={
            "data": {
                "localTripId": "trip-1",
                "title": "Morning Walk",
                "startedAt": "2026-05-10T06:00:00Z",
            }
        },
        headers={"Authorization": f"Bearer {wfr_auth_token}"},
    )

    response = client.get(
        "/api/wildlife-field-recorder/trips",
        headers={"Authorization": f"Bearer {wfr_auth_token}"},
    )
    assert response.status_code == 200
    json = response.json()
    assert json["total"] == 1
    assert json["records"][0]["data"]["title"] == "Morning Walk"


def test_update_trip_route_geojson(client, wfr_auth_token):
    create_resp = client.post(
        "/api/wildlife-field-recorder/trips",
        json={
            "data": {
                "localTripId": "trip-geo-1",
                "title": "Route Test",
                "startedAt": "2026-05-10T20:00:00Z",
                "routeGeoJson": {"type": "FeatureCollection", "features": []},
            }
        },
        headers={"Authorization": f"Bearer {wfr_auth_token}"},
    )
    record_id = create_resp.json()["id"]

    # PATCH replaces the full data document, so include all required fields
    response = client.patch(
        f"/api/wildlife-field-recorder/trips/{record_id}",
        json={
            "data": {
                "localTripId": "trip-geo-1",
                "title": "Route Test Updated",
                "startedAt": "2026-05-10T20:00:00Z",
                "routeGeoJson": {
                    "type": "FeatureCollection",
                    "features": [
                        {
                            "type": "Feature",
                            "geometry": {
                                "type": "LineString",
                                "coordinates": [[-87.5675, 38.3553], [-87.5680, 38.3560]],
                            },
                            "properties": {"name": "Evening Drive Route"},
                        }
                    ],
                }
            }
        },
        headers={"Authorization": f"Bearer {wfr_auth_token}"},
    )
    assert response.status_code == 200
    updated = response.json()
    assert updated["data"]["title"] == "Route Test Updated"
    assert updated["data"]["routeGeoJson"]["type"] == "FeatureCollection"
    assert len(updated["data"]["routeGeoJson"]["features"]) == 1
    assert updated["data"]["routeGeoJson"]["features"][0]["geometry"]["type"] == "LineString"
