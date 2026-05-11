import json
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.loader import get_registry
from app.db.models import RecordModel, utc_now
from app.db.session import get_session_factory


class RecordError(RuntimeError):
    pass


def _validate_app_resource(app_id: str, resource: str) -> None:
    registry = get_registry()
    app = registry.get_app(app_id)
    if app is None:
        raise RecordError(f"App not found: {app_id}")
    res = registry.get_resource(app_id, resource)
    if res is None:
        raise RecordError(f"Resource not found: {app_id}/{resource}")
    return None


def _validate_fields(app_id: str, resource: str, data: dict) -> None:
    registry = get_registry()
    res = registry.get_resource(app_id, resource)
    if res is None:
        return
    for field_name, field_config in res.fields.items():
        if field_config.required and field_name not in data:
            raise RecordError(f"Required field missing: {field_name}")


def list_records(app_id: str, resource: str, include_deleted: bool = False) -> list[RecordModel]:
    _validate_app_resource(app_id, resource)
    session: Session = get_session_factory()()
    try:
        query = select(RecordModel).where(
            RecordModel.app_id == app_id,
            RecordModel.resource == resource,
        )
        if not include_deleted:
            query = query.where(RecordModel.deleted_at.is_(None))
        query = query.order_by(RecordModel.created_at.desc())
        return list(session.scalars(query).all())
    finally:
        session.close()


def create_record(
    app_id: str,
    resource: str,
    data: dict,
    created_by_token_id: str | None = None,
) -> RecordModel:
    _validate_app_resource(app_id, resource)
    _validate_fields(app_id, resource, data)

    record_id = str(uuid.uuid4())
    session: Session = get_session_factory()()
    try:
        model = RecordModel(
            id=record_id,
            app_id=app_id,
            resource=resource,
            data_json=json.dumps(data),
            created_by_token_id=created_by_token_id,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        session.add(model)
        session.commit()
        session.refresh(model)
        return model
    finally:
        session.close()


def get_record(record_id: str) -> RecordModel | None:
    session: Session = get_session_factory()()
    try:
        return session.scalar(select(RecordModel).where(RecordModel.id == record_id))
    finally:
        session.close()


def update_record(record_id: str, data: dict) -> RecordModel:
    from sqlalchemy import select
    session: Session = get_session_factory()()
    try:
        record = session.scalar(select(RecordModel).where(RecordModel.id == record_id))
        if record is None:
            raise RecordError(f"Record not found: {record_id}")
        if record.deleted_at is not None:
            raise RecordError(f"Record is deleted: {record_id}")

        if data is not None:
            _validate_fields(record.app_id, record.resource, data)
            record.data_json = json.dumps(data)
            record.updated_at = utc_now()

        session.commit()
        return record
    finally:
        session.close()


def soft_delete_record(record_id: str) -> RecordModel:
    from sqlalchemy import select
    session: Session = get_session_factory()()
    try:
        record = session.scalar(select(RecordModel).where(RecordModel.id == record_id))
        if record is None:
            raise RecordError(f"Record not found: {record_id}")
        record.deleted_at = utc_now()
        session.commit()
        return record
    finally:
        session.close()
