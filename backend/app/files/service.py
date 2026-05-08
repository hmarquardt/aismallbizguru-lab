import hashlib
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.loader import get_registry
from app.db.models import FileModel, utc_now
from app.db.session import get_session_factory
from app.files.storage import StorageError, delete_file, generate_object_key, put_file


class FileServiceError(RuntimeError):
    pass


def _get_file_settings(app_id: str, resource: str) -> dict:
    registry = get_registry()
    app = registry.get_app(app_id)
    if app is None:
        raise FileServiceError(f"App not found: {app_id}")
    res = registry.get_resource(app_id, resource)
    if res is None:
        raise FileServiceError(f"Resource not found: {app_id}/{resource}")
    if not res.files.enabled:
        raise FileServiceError(f"File storage not enabled for this resource: {app_id}/{resource}")
    return {
        "enabled": res.files.enabled,
        "allowed_types": res.files.allowed_types,
        "max_size_mb": res.files.max_size_mb,
    }


def list_files(app_id: str, resource: str, record_id: str) -> list[FileModel]:
    _get_file_settings(app_id, resource)
    session: Session = get_session_factory()()
    try:
        files = session.scalars(
            select(FileModel)
            .where(
                FileModel.app_id == app_id,
                FileModel.resource == resource,
                FileModel.record_id == record_id,
                FileModel.deleted_at.is_(None),
            )
            .order_by(FileModel.created_at.desc())
        ).all()
        return list(files)
    finally:
        session.close()


def create_file(
    app_id: str,
    resource: str,
    record_id: str,
    filename: str,
    content_type: str,
    data: bytes,
) -> FileModel:
    file_settings = _get_file_settings(app_id, resource)

    if file_settings["allowed_types"] and content_type not in file_settings["allowed_types"]:
        raise FileServiceError(f"Content type {content_type} not allowed")

    max_size = file_settings.get("max_size_mb")
    if max_size and len(data) > max_size * 1024 * 1024:
        raise FileServiceError(f"File exceeds maximum size of {max_size}MB")

    checksum = hashlib.sha256(data).hexdigest()
    object_key = generate_object_key(app_id, record_id, filename)

    try:
        put_file(object_key, data, content_type, len(data))
    except StorageError as e:
        raise FileServiceError(f"Failed to store file: {e}")

    file_id = str(uuid.uuid4())
    session: Session = get_session_factory()()
    try:
        model = FileModel(
            id=file_id,
            app_id=app_id,
            resource=resource,
            record_id=record_id,
            bucket=object_key.split("/")[0],
            object_key=object_key,
            filename=filename,
            content_type=content_type,
            size_bytes=len(data),
            checksum=checksum,
            created_at=utc_now(),
        )
        session.add(model)
        session.commit()
        session.refresh(model)
        return model
    finally:
        session.close()


def get_file_metadata(file_id: str) -> FileModel | None:
    session: Session = get_session_factory()()
    try:
        return session.scalar(select(FileModel).where(FileModel.id == file_id))
    finally:
        session.close()


def delete_file_record(file_id: str) -> None:
    model = get_file_metadata(file_id)
    if model is None:
        raise FileServiceError("File not found")

    if model.deleted_at is not None:
        raise FileServiceError("File already deleted")

    try:
        delete_file(model.object_key)
    except StorageError:
        pass

    session: Session = get_session_factory()()
    try:
        model.deleted_at = utc_now()
        session.commit()
    finally:
        session.close()


def rename_file_record(file_id: str, filename: str) -> FileModel:
    clean_name = filename.strip()
    if not clean_name:
        raise FileServiceError("Filename is required")

    session: Session = get_session_factory()()
    try:
        model = session.scalar(select(FileModel).where(FileModel.id == file_id))
        if model is None or model.deleted_at is not None:
            raise FileServiceError("File not found")
        model.filename = clean_name
        session.commit()
        session.refresh(model)
        return model
    finally:
        session.close()
