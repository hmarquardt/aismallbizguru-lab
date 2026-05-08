import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from app.backups.runner import BackupRunError, run_backup_now
from app.db.init_db import init_db


def _scheduled_time() -> tuple[int, int]:
    raw = os.environ.get("BACKUP_SCHEDULE_TIME", "03:30")
    hour, minute = raw.split(":", 1)
    return int(hour), int(minute)


def main() -> None:
    init_db()
    tz = ZoneInfo(os.environ.get("TZ", "UTC"))
    schedule_hour, schedule_minute = _scheduled_time()
    last_run_date: str | None = None

    print(f"LabBox worker started; nightly backup scheduled at {schedule_hour:02d}:{schedule_minute:02d}", flush=True)

    while True:
        now = datetime.now(tz)
        today = now.date().isoformat()
        should_run = (
            now.hour == schedule_hour
            and now.minute == schedule_minute
            and last_run_date != today
        )

        if should_run:
            print("Starting scheduled backup", flush=True)
            try:
                run_id = run_backup_now()
                print(f"Scheduled backup complete: {run_id}", flush=True)
            except BackupRunError as exc:
                print(f"Scheduled backup failed: {exc}", flush=True)
            last_run_date = today

        time.sleep(30)


if __name__ == "__main__":
    main()
