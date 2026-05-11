from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config.loader import AppConfigRegistry, get_registry
from app.db.models import AppModel, Base, utc_now
from app.db.session import get_engine, get_session_factory


def create_tables() -> None:
    Base.metadata.create_all(bind=get_engine())
    add_missing_columns()


def add_missing_columns() -> None:
    columns = {
        "records": {
            "created_by_token_id": "TEXT",
        },
        "files": {
            "created_by_token_id": "TEXT",
        },
    }
    with get_engine().begin() as connection:
        for table_name, expected_columns in columns.items():
            existing_columns = {
                row[1] for row in connection.execute(text(f"PRAGMA table_info({table_name})")).all()
            }
            for column_name, column_type in expected_columns.items():
                if column_name not in existing_columns:
                    connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"))


def sync_configured_apps(session: Session, registry: AppConfigRegistry | None = None) -> None:
    app_registry = registry or get_registry()

    for app_id, app_config in app_registry.list_apps().items():
        app = session.scalar(select(AppModel).where(AppModel.id == app_id))
        if app is None:
            session.add(
                AppModel(
                    id=app_id,
                    name=app_config.title,
                    description=app_config.description,
                    config_version=app_config.config_version,
                )
            )
        else:
            app.name = app_config.title
            app.description = app_config.description
            app.config_version = app_config.config_version
            app.updated_at = utc_now()


def init_db() -> None:
    create_tables()
    with get_session_factory()() as session:
        sync_configured_apps(session)
        session.commit()
