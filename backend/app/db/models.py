from datetime import datetime, timezone

from sqlalchemy import Boolean, ForeignKey, Integer, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Base(DeclarativeBase):
    pass


class AppModel(Base):
    __tablename__ = "apps"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    config_version: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, default=utc_now, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, default=utc_now, onupdate=utc_now, nullable=False)


class RecordModel(Base):
    __tablename__ = "records"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    app_id: Mapped[str] = mapped_column(ForeignKey("apps.id"), nullable=False)
    resource: Mapped[str] = mapped_column(Text, nullable=False)
    data_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_by_token_id: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, default=utc_now, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, default=utc_now, onupdate=utc_now, nullable=False)
    deleted_at: Mapped[str | None] = mapped_column(Text)


class FileModel(Base):
    __tablename__ = "files"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    app_id: Mapped[str] = mapped_column(ForeignKey("apps.id"), nullable=False)
    resource: Mapped[str | None] = mapped_column(Text)
    record_id: Mapped[str | None] = mapped_column(Text)
    bucket: Mapped[str] = mapped_column(Text, nullable=False)
    object_key: Mapped[str] = mapped_column(Text, nullable=False)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str | None] = mapped_column(Text)
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    checksum: Mapped[str | None] = mapped_column(Text)
    created_by_token_id: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, default=utc_now, nullable=False)
    deleted_at: Mapped[str | None] = mapped_column(Text)


class ProxySourceModel(Base):
    __tablename__ = "proxy_sources"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    config_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, default=utc_now, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, default=utc_now, onupdate=utc_now, nullable=False)
    deleted_at: Mapped[str | None] = mapped_column(Text)


class ApiTokenModel(Base):
    __tablename__ = "api_tokens"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    scopes_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, default=utc_now, nullable=False)
    expires_at: Mapped[str | None] = mapped_column(Text)
    revoked_at: Mapped[str | None] = mapped_column(Text)


class EventModel(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    app_id: Mapped[str | None] = mapped_column(Text)
    actor: Mapped[str | None] = mapped_column(Text)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    resource: Mapped[str | None] = mapped_column(Text)
    record_id: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, default=utc_now, nullable=False)


class JobModel(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    app_id: Mapped[str | None] = mapped_column(Text)
    job_type: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    run_after: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, default=utc_now, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, default=utc_now, onupdate=utc_now, nullable=False)


class BackupRunModel(Base):
    __tablename__ = "backup_runs"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[str] = mapped_column(Text, nullable=False)
    finished_at: Mapped[str | None] = mapped_column(Text)
    destination: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_id: Mapped[str | None] = mapped_column(Text)
    bytes_added: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)
