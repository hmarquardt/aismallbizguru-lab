from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.loader import AppConfigRegistry, get_registry
from app.db.models import AppModel, Base, utc_now
from app.db.session import get_engine, get_session_factory


def create_tables() -> None:
    Base.metadata.create_all(bind=get_engine())


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
