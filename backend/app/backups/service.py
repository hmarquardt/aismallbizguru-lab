import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import BackupRunModel, utc_now
from app.db.session import get_session_factory


class BackupServiceError(RuntimeError):
    pass


def start_backup_run(destination: str) -> str:
    run_id = str(uuid.uuid4())
    session: Session = get_session_factory()()
    try:
        model = BackupRunModel(
            id=run_id,
            status="running",
            started_at=utc_now(),
            destination=destination,
        )
        session.add(model)
        session.commit()
        return run_id
    finally:
        session.close()


def finish_backup_run_success(run_id: str, snapshot_id: str, bytes_added: int | None = None) -> None:
    session: Session = get_session_factory()()
    try:
        model = session.scalar(select(BackupRunModel).where(BackupRunModel.id == run_id))
        if model is None:
            return
        model.status = "success"
        model.finished_at = utc_now()
        model.snapshot_id = snapshot_id
        model.bytes_added = bytes_added
        session.commit()
    finally:
        session.close()


def finish_backup_run_failure(run_id: str, error: str) -> None:
    session: Session = get_session_factory()()
    try:
        model = session.scalar(select(BackupRunModel).where(BackupRunModel.id == run_id))
        if model is None:
            return
        model.status = "failed"
        model.finished_at = utc_now()
        model.error = error
        session.commit()
    finally:
        session.close()


def get_latest_backup_run() -> BackupRunModel | None:
    session: Session = get_session_factory()()
    try:
        return session.scalar(
            select(BackupRunModel).order_by(BackupRunModel.started_at.desc()).limit(1)
        )
    finally:
        session.close()


def list_backup_runs(limit: int = 50) -> list[BackupRunModel]:
    session: Session = get_session_factory()()
    try:
        return list(session.scalars(
            select(BackupRunModel).order_by(BackupRunModel.started_at.desc()).limit(limit)
        ).all())
    finally:
        session.close()