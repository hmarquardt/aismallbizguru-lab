from sqlalchemy import inspect, select, text

from app.config.loader import get_registry
from app.db.init_db import init_db
from app.db.models import AppModel
from app.db.session import clear_engine_cache, get_engine, get_session_factory
from app.settings import get_settings


def configure_test_db(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "labbox.db"))
    get_settings.cache_clear()
    clear_engine_cache()


def test_init_db_creates_tables(tmp_path, monkeypatch) -> None:
    configure_test_db(tmp_path, monkeypatch)

    init_db()

    table_names = set(inspect(get_engine()).get_table_names())
    assert {
        "apps",
        "records",
        "files",
        "api_tokens",
        "events",
        "jobs",
        "backup_runs",
    }.issubset(table_names)

    inspector = inspect(get_engine())
    record_columns = {column["name"] for column in inspector.get_columns("records")}
    file_columns = {column["name"] for column in inspector.get_columns("files")}
    assert "created_by_token_id" in record_columns
    assert "created_by_token_id" in file_columns


def test_sqlite_pragmas_are_enabled(tmp_path, monkeypatch) -> None:
    configure_test_db(tmp_path, monkeypatch)

    with get_engine().connect() as connection:
        assert connection.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
        assert connection.execute(text("PRAGMA busy_timeout")).scalar_one() == 5000
        assert connection.execute(text("PRAGMA journal_mode")).scalar_one() == "wal"
        assert connection.execute(text("PRAGMA synchronous")).scalar_one() == 1


def test_init_db_syncs_configured_apps(tmp_path, monkeypatch) -> None:
    configure_test_db(tmp_path, monkeypatch)

    init_db()

    with get_session_factory()() as session:
        app = session.scalar(select(AppModel).where(AppModel.id == "junk-drawer"))

    assert app is not None
    assert app.name == get_registry().get_app("junk-drawer").title
