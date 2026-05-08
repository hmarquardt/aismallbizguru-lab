# Backup and Restore

LabBox uses Restic for encrypted off-box backups to Cloudflare R2.

## Backup

Backups are run by:

```bash
scripts/backup_now.sh
```

The script:

- creates a consistent SQLite backup with `sqlite3 .backup`
- backs up config files
- backs up MinIO object data
- backs up deployment files
- applies the configured Restic retention policy

Required environment variables are loaded from the process environment or from `/opt/labbox/.env` when run on the host.

The `.env` file is not backed up by default. Set this only if you intentionally want `.env` included in the encrypted Restic repository:

```env
BACKUP_INCLUDE_ENV=true
```

## Manual Backup

On the VPS:

```bash
cd /opt/labbox
docker compose exec api bash /app/scripts/backup_now.sh
```

## Restore Latest Snapshot

Restore never overwrites live data by default. Choose an empty directory:

```bash
mkdir -p /tmp/labbox-restore
scripts/restore_latest.sh /tmp/labbox-restore
```

If running from inside Docker:

```bash
docker compose exec api bash /app/scripts/restore_latest.sh /tmp/labbox-restore
```

## Restore SQLite

After restoring, locate the staged SQLite backup:

```bash
find /tmp/labbox-restore -name labbox.db
```

Stop the stack before replacing live SQLite data:

```bash
cd /opt/labbox
docker compose down
cp /tmp/labbox-restore/backup-staging/*/sqlite/labbox.db /opt/labbox/data/sqlite/labbox.db
docker compose up -d
```

## Restore MinIO Data

Stop the stack, copy restored MinIO data into place, then restart:

```bash
cd /opt/labbox
docker compose down
rsync -a /tmp/labbox-restore/data/minio/ /opt/labbox/data/minio/
docker compose up -d
```

## Verify

After restore:

```bash
curl https://labs.smallbizguru.com/api/health
docker compose logs --tail=100 api
```
