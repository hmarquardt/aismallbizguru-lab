from app.backups.runner import _extract_snapshot_id


def test_extract_snapshot_id_from_restic_backup_output() -> None:
    output = """
no parent snapshot found, will read all files
snapshot 475e735d saved
[backup] applying retention policy
"""

    assert _extract_snapshot_id(output) == "475e735d"


def test_extract_snapshot_id_ignores_retention_table_reason_lines() -> None:
    output = """
keep 1 snapshots:
ID        Time                 Host          Tags        Reasons
475e735d  2026-05-15 19:06:06  host          labbox      daily snapshot
"""

    assert _extract_snapshot_id(output) == ""
