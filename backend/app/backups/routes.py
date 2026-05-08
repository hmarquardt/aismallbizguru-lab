from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.dependencies import get_admin_session
from app.backups.runner import BackupRunError, run_backup_now
from app.backups.service import list_backup_runs


router = APIRouter(prefix="/api/admin", tags=["admin-api"])


@router.get("/backups")
def get_backups(session: Annotated[str | None, Depends(get_admin_session)]) -> dict:
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    runs = list_backup_runs()
    return {
        "runs": [{
            "id": r.id,
            "status": r.status,
            "started_at": r.started_at,
            "finished_at": r.finished_at,
            "destination": r.destination,
            "snapshot_id": r.snapshot_id,
            "bytes_added": r.bytes_added,
            "error": r.error,
        } for r in runs]
    }


@router.post("/backups/run")
def trigger_backup(session: Annotated[str | None, Depends(get_admin_session)]) -> dict[str, str]:
    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        run_id = run_backup_now()
    except BackupRunError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    return {"status": "success", "run_id": run_id}
