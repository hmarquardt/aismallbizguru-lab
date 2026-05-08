from collections.abc import Generator
from functools import lru_cache
from pathlib import Path

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.settings import get_settings


def sqlite_url(sqlite_path: str) -> str:
    return f"sqlite:///{sqlite_path}"


def configure_sqlite_pragmas(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def set_pragmas(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()


def create_sqlite_engine(sqlite_path: str) -> Engine:
    path = Path(sqlite_path)
    if path.parent:
        path.parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(
        sqlite_url(sqlite_path),
        connect_args={"check_same_thread": False},
        future=True,
    )
    configure_sqlite_pragmas(engine)
    return engine


@lru_cache
def get_engine() -> Engine:
    return create_sqlite_engine(get_settings().sqlite_path)


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, future=True, expire_on_commit=False)


def get_session() -> Generator[Session]:
    with get_session_factory()() as session:
        yield session


def check_db() -> bool:
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def clear_engine_cache() -> None:
    if get_engine.cache_info().currsize:
        get_engine().dispose()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
