from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.init_db import init_db
from app.db.models import ApiTokenModel, FileModel, RecordModel, utc_now
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


def test_admin_tokens_page_renders_scope_presets(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "labbox.db"))
    monkeypatch.setenv("ADMIN_SESSION_SECRET", "test-session")
    get_settings.cache_clear()
    clear_engine_cache()

    with TestClient(app) as client:
        client.cookies.set("session", "test-session")
        response = client.get("/admin/tokens")

    assert response.status_code == 200
    assert "Top Hat Ferals read/write" in response.text
    assert '{"top-hat-ferals": ["read", "write"]}' in response.text


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


def test_admin_record_ajax_create_returns_json_status(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "labbox.db"))
    monkeypatch.setenv("ADMIN_SESSION_SECRET", "test-session")
    get_settings.cache_clear()
    clear_engine_cache()

    with TestClient(app) as client:
        init_db()
        client.cookies.set("session", "test-session")
        response = client.post(
            "/admin/apps/junk-drawer/notes/new",
            data={"title": "Ajax Note", "body": "Created in admin", "tags": '["admin"]'},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["message"] == "Record created"
    assert payload["location"].startswith("/admin/records/")


def test_admin_record_ajax_validation_returns_json_error(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "labbox.db"))
    monkeypatch.setenv("ADMIN_SESSION_SECRET", "test-session")
    get_settings.cache_clear()
    clear_engine_cache()

    with TestClient(app) as client:
        init_db()
        client.cookies.set("session", "test-session")
        response = client.post(
            "/admin/apps/junk-drawer/notes/new",
            data={"body": "Missing title"},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

    assert response.status_code == 400
    payload = response.json()
    assert payload["ok"] is False
    assert "Title is required" in payload["message"]


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


def test_admin_ajax_delete_record_returns_status(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "labbox.db"))
    monkeypatch.setenv("ADMIN_SESSION_SECRET", "test-session")
    get_settings.cache_clear()
    clear_engine_cache()

    with TestClient(app) as client:
        init_db()
        record = create_record("junk-drawer", "notes", {"title": "Ajax Delete Me"})
        client.cookies.set("session", "test-session")
        response = client.post(
            f"/admin/records/{record.id}/delete",
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

    assert response.status_code == 200
    assert response.json()["message"] == "Record deleted"

    session = get_session_factory()()
    try:
        deleted = session.scalar(select(RecordModel).where(RecordModel.id == record.id))
        assert deleted is not None
        assert deleted.deleted_at is not None
    finally:
        session.close()


def test_admin_records_page_filters_by_app_and_uses_json_pills(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "labbox.db"))
    monkeypatch.setenv("ADMIN_SESSION_SECRET", "test-session")
    get_settings.cache_clear()
    clear_engine_cache()

    with TestClient(app) as client:
        init_db()
        session = get_session_factory()()
        try:
            session.add(
                ApiTokenModel(
                    id="token-record-display",
                    name="Record Display Token",
                    token_hash="hashed-token",
                    scopes_json='{"wildlife-field-recorder": ["read", "write"]}',
                    created_at=utc_now(),
                )
            )
            session.commit()
        finally:
            session.close()
        create_record("junk-drawer", "notes", {"title": "Admin Note"})
        create_record(
            "wildlife-field-recorder",
            "observations",
            {
                "localId": "obs-admin-filter",
                "createdAt": "2026-05-11T10:00:00Z",
            },
            created_by_token_id="token-record-display",
        )
        client.cookies.set("session", "test-session")
        response = client.get("/admin/records?app_id=wildlife-field-recorder")

    assert response.status_code == 200
    assert "data-json=" in response.text
    assert "obs-admin-filter" in response.text
    assert "Admin Note" not in response.text
    assert "Record Display Token" in response.text
    assert 'value="wildlife-field-recorder" selected' in response.text


def test_admin_can_delete_file(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "labbox.db"))
    monkeypatch.setenv("ADMIN_SESSION_SECRET", "test-session")
    monkeypatch.setattr("app.files.service.delete_file", lambda _object_key: None)
    get_settings.cache_clear()
    clear_engine_cache()

    with TestClient(app) as client:
        init_db()
        record = create_record("junk-drawer", "notes", {"title": "File Owner"})
        session = get_session_factory()()
        try:
            session.add(
                FileModel(
                    id="admin-file-delete",
                    app_id="junk-drawer",
                    resource="notes",
                    record_id=record.id,
                    bucket="labbox-assets",
                    object_key=f"junk-drawer/{record.id}/admin-file-delete.webp",
                    filename="admin-file-delete.webp",
                    content_type="image/webp",
                    size_bytes=12,
                    checksum="abc123",
                    created_at=utc_now(),
                )
            )
            session.commit()
        finally:
            session.close()

        client.cookies.set("session", "test-session")
        response = client.post(
            "/admin/files/admin-file-delete/delete",
            data={"next_url": "/admin/files"},
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert response.headers["Location"] == "/admin/files"

    session = get_session_factory()()
    try:
        deleted = session.scalar(select(FileModel).where(FileModel.id == "admin-file-delete"))
        assert deleted is not None
        assert deleted.deleted_at is not None
    finally:
        session.close()


def test_admin_ajax_delete_file_returns_status(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "labbox.db"))
    monkeypatch.setenv("ADMIN_SESSION_SECRET", "test-session")
    monkeypatch.setattr("app.files.service.delete_file", lambda _object_key: None)
    get_settings.cache_clear()
    clear_engine_cache()

    with TestClient(app) as client:
        init_db()
        record = create_record("junk-drawer", "notes", {"title": "File Owner"})
        session = get_session_factory()()
        try:
            session.add(
                FileModel(
                    id="admin-file-ajax-delete",
                    app_id="junk-drawer",
                    resource="notes",
                    record_id=record.id,
                    bucket="labbox-assets",
                    object_key=f"junk-drawer/{record.id}/admin-file-ajax-delete.webp",
                    filename="admin-file-ajax-delete.webp",
                    content_type="image/webp",
                    size_bytes=12,
                    checksum="abc123",
                    created_at=utc_now(),
                )
            )
            session.commit()
        finally:
            session.close()

        client.cookies.set("session", "test-session")
        response = client.post(
            "/admin/files/admin-file-ajax-delete/delete",
            data={"next_url": "/admin/files"},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

    assert response.status_code == 200
    assert response.json()["message"] == "File deleted"


def test_admin_files_page_filters_by_app(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "labbox.db"))
    monkeypatch.setenv("ADMIN_SESSION_SECRET", "test-session")
    get_settings.cache_clear()
    clear_engine_cache()

    with TestClient(app) as client:
        init_db()
        session = get_session_factory()()
        try:
            session.add(
                ApiTokenModel(
                    id="token-file-display",
                    name="File Display Token",
                    token_hash="hashed-token",
                    scopes_json='{"wildlife-field-recorder": ["read", "write"]}',
                    created_at=utc_now(),
                )
            )
            session.add_all([
                FileModel(
                    id="admin-file-junk",
                    app_id="junk-drawer",
                    resource="notes",
                    record_id="record-junk",
                    bucket="labbox-assets",
                    object_key="junk-drawer/record-junk/admin-file-junk.txt",
                    filename="admin-file-junk.txt",
                    content_type="text/plain",
                    size_bytes=12,
                    checksum="abc123",
                    created_at=utc_now(),
                ),
                FileModel(
                    id="admin-file-wfr",
                    app_id="wildlife-field-recorder",
                    resource="observations",
                    record_id="record-wfr",
                    bucket="labbox-assets",
                    object_key="wildlife-field-recorder/record-wfr/admin-file-wfr.jpg",
                    filename="admin-file-wfr.jpg",
                    content_type="image/jpeg",
                    size_bytes=24,
                    checksum="def456",
                    created_by_token_id="token-file-display",
                    created_at=utc_now(),
                ),
            ])
            session.commit()
        finally:
            session.close()

        client.cookies.set("session", "test-session")
        response = client.get("/admin/files?app_id=wildlife-field-recorder")

    assert response.status_code == 200
    assert "admin-file-wfr.jpg" in response.text
    assert "admin-file-junk.txt" not in response.text
    assert "File Display Token" in response.text
    assert 'value="wildlife-field-recorder" selected' in response.text


def test_admin_token_create_saves_json_scopes(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "labbox.db"))
    monkeypatch.setenv("ADMIN_SESSION_SECRET", "test-session")
    get_settings.cache_clear()
    clear_engine_cache()

    with TestClient(app) as client:
        init_db()
        client.cookies.set("session", "test-session")
        response = client.post(
            "/admin/tokens",
            data={"name": "Top Hat", "scopes": '{"top-hat-ferals": ["read", "write"]}'},
            follow_redirects=False,
        )

    assert response.status_code == 303

    session = get_session_factory()()
    try:
        token = session.scalar(select(ApiTokenModel).where(ApiTokenModel.name == "Top Hat"))
        assert token is not None
        assert token.scopes_json == '{"top-hat-ferals": ["read", "write"]}'
    finally:
        session.close()


def test_admin_token_create_accepts_shorthand_scopes(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "labbox.db"))
    monkeypatch.setenv("ADMIN_SESSION_SECRET", "test-session")
    get_settings.cache_clear()
    clear_engine_cache()

    with TestClient(app) as client:
        init_db()
        client.cookies.set("session", "test-session")
        response = client.post(
            "/admin/tokens",
            data={"name": "Top Hat Shorthand", "scopes": "top-hat-ferals:read,top-hat-ferals:write"},
            follow_redirects=False,
        )

    assert response.status_code == 303

    session = get_session_factory()()
    try:
        token = session.scalar(select(ApiTokenModel).where(ApiTokenModel.name == "Top Hat Shorthand"))
        assert token is not None
        assert token.scopes_json == '{"top-hat-ferals": ["read", "write"]}'
    finally:
        session.close()


def test_admin_token_create_rejects_invalid_scopes(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "labbox.db"))
    monkeypatch.setenv("ADMIN_SESSION_SECRET", "test-session")
    get_settings.cache_clear()
    clear_engine_cache()

    with TestClient(app) as client:
        init_db()
        client.cookies.set("session", "test-session")
        response = client.post(
            "/admin/tokens",
            data={"name": "Bad Token", "scopes": "{not-json"},
        )

    assert response.status_code == 200
    assert "Scopes JSON is invalid" in response.text

    session = get_session_factory()()
    try:
        token = session.scalar(select(ApiTokenModel).where(ApiTokenModel.name == "Bad Token"))
        assert token is None
    finally:
        session.close()


def test_admin_can_permanently_delete_token(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "labbox.db"))
    monkeypatch.setenv("ADMIN_SESSION_SECRET", "test-session")
    get_settings.cache_clear()
    clear_engine_cache()

    with TestClient(app) as client:
        init_db()
        session = get_session_factory()()
        try:
            session.add(
                ApiTokenModel(
                    id="token-delete-me",
                    name="Delete Me",
                    token_hash="hashed-token",
                    scopes_json='{"junk-drawer": ["read"]}',
                    created_at=utc_now(),
                )
            )
            session.commit()
        finally:
            session.close()

        client.cookies.set("session", "test-session")
        response = client.post("/admin/tokens/token-delete-me/delete", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["Location"] == "/admin/tokens"

    session = get_session_factory()()
    try:
        token = session.scalar(select(ApiTokenModel).where(ApiTokenModel.id == "token-delete-me"))
        assert token is None
    finally:
        session.close()


def test_admin_ajax_token_create_returns_token_once(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "labbox.db"))
    monkeypatch.setenv("ADMIN_SESSION_SECRET", "test-session")
    get_settings.cache_clear()
    clear_engine_cache()

    with TestClient(app) as client:
        init_db()
        client.cookies.set("session", "test-session")
        response = client.post(
            "/admin/tokens",
            data={"name": "Ajax Token", "scopes": '{"junk-drawer": ["read"]}'},
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["message"].startswith("Token created")
    assert payload["token"]


def test_admin_ajax_token_delete_returns_status(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "labbox.db"))
    monkeypatch.setenv("ADMIN_SESSION_SECRET", "test-session")
    get_settings.cache_clear()
    clear_engine_cache()

    with TestClient(app) as client:
        init_db()
        session = get_session_factory()()
        try:
            session.add(
                ApiTokenModel(
                    id="token-ajax-delete-me",
                    name="Delete Me Ajax",
                    token_hash="hashed-token",
                    scopes_json='{"junk-drawer": ["read"]}',
                    created_at=utc_now(),
                )
            )
            session.commit()
        finally:
            session.close()

        client.cookies.set("session", "test-session")
        response = client.post(
            "/admin/tokens/token-ajax-delete-me/delete",
            headers={"X-Requested-With": "XMLHttpRequest"},
        )

    assert response.status_code == 200
    assert response.json()["message"] == "Token deleted"
