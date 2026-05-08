import uuid
from io import BytesIO
from typing import BinaryIO
from urllib.parse import urlparse

from minio import Minio
from minio.error import S3Error

from app.settings import get_settings


class StorageError(RuntimeError):
    pass


def _get_client() -> Minio:
    settings = get_settings()
    endpoint = settings.minio_endpoint
    secure = settings.minio_secure
    parsed = urlparse(endpoint)
    if parsed.scheme:
        endpoint = parsed.netloc
        secure = parsed.scheme == "https"
    return Minio(
        endpoint=endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=secure,
    )


def generate_object_key(app_id: str, record_id: str, filename: str) -> str:
    safe_name = "".join(c if c.isalnum() or c in ".-_" else "_" for c in filename)
    unique = uuid.uuid4().hex[:8]
    return f"{app_id}/{record_id}/{unique}_{safe_name}"


def put_file(object_key: str, data: BinaryIO | bytes, content_type: str, size: int) -> None:
    try:
        client = _get_client()
        settings = get_settings()
        stream = BytesIO(data) if isinstance(data, bytes) else data
        client.put_object(
            bucket_name=settings.minio_bucket,
            object_name=object_key,
            data=stream,
            length=size,
            content_type=content_type,
        )
    except S3Error as e:
        raise StorageError(f"Failed to upload file: {e}")


def get_file(object_key: str) -> BinaryIO:
    try:
        client = _get_client()
        settings = get_settings()
        response = client.get_object(bucket_name=settings.minio_bucket, object_name=object_key)
        return response
    except S3Error as e:
        raise StorageError(f"Failed to download file: {e}")


def delete_file(object_key: str) -> None:
    try:
        client = _get_client()
        settings = get_settings()
        client.remove_object(bucket_name=settings.minio_bucket, object_name=object_key)
    except S3Error as e:
        raise StorageError(f"Failed to delete file: {e}")


def file_exists(object_key: str) -> bool:
    try:
        client = _get_client()
        settings = get_settings()
        client.stat_object(bucket_name=settings.minio_bucket, object_name=object_key)
        return True
    except S3Error:
        return False


def ensure_bucket_exists() -> None:
    settings = get_settings()
    client = _get_client()
    if not client.bucket_exists(settings.minio_bucket):
        client.make_bucket(settings.minio_bucket)
