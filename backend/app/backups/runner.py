import os
import subprocess

from app.backups.service import finish_backup_run_failure, finish_backup_run_success, start_backup_run


class BackupRunError(RuntimeError):
    pass


def run_backup_now(timeout_seconds: int = 900) -> str:
    backup_script = os.environ.get("BACKUP_SCRIPT", "/app/scripts/backup_now.sh")
    run_id = start_backup_run("restic:r2")

    try:
        result = subprocess.run(
            ["bash", backup_script],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        finish_backup_run_failure(run_id, f"Backup timed out after {timeout_seconds} seconds")
        raise BackupRunError("Backup timed out") from exc
    except FileNotFoundError as exc:
        message = f"Backup script not found: {backup_script}"
        finish_backup_run_failure(run_id, message)
        raise BackupRunError(message) from exc

    if result.returncode != 0:
        error = (result.stderr or result.stdout or "Backup failed").strip()[:500]
        finish_backup_run_failure(run_id, error)
        raise BackupRunError(error)

    snapshot_id = _extract_snapshot_id(result.stdout)
    finish_backup_run_success(run_id, snapshot_id)
    return run_id


def _extract_snapshot_id(output: str) -> str:
    for line in output.splitlines():
        lowered = line.lower()
        if "snapshot" in lowered or "id:" in lowered:
            return line.strip()
    return ""
