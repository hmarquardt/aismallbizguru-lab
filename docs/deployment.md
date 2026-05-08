# Deployment

Target host:

```text
https://lab.aismallbizguru.com
```

This repo is expected to already exist on GitHub. Do not commit real secrets.

## DNS

Create an `A` record for `lab.aismallbizguru.com` pointing at the Hetzner VPS IPv4 address.

## VPS Setup

On a fresh Ubuntu/Debian VPS:

```bash
sudo bash scripts/vps_setup.sh
```

Then place the repo at `/opt/labbox`.

## Secrets

Create the server env file:

```bash
cd /opt/labbox
cp .env.example .env
chmod 600 .env
```

Confirm Git ignores it:

```bash
git status --short
```

Generate required values:

```bash
openssl rand -base64 48
```

Use that for `ADMIN_SESSION_SECRET`, `API_TOKEN_PEPPER`, and `RESTIC_PASSWORD`.

Generate the admin password hash:

```bash
cd /opt/labbox
docker compose run --rm api python /app/scripts/create_admin_hash.py
```

Fill these in `/opt/labbox/.env`:

```text
ADMIN_PASSWORD_HASH
ADMIN_SESSION_SECRET
API_TOKEN_PEPPER
MINIO_ROOT_USER
MINIO_ROOT_PASSWORD
S3_ACCESS_KEY
S3_SECRET_KEY
R2_ACCOUNT_ID
R2_ACCESS_KEY_ID
R2_SECRET_ACCESS_KEY
RESTIC_PASSWORD
```

Create the Cloudflare R2 bucket:

```text
lab-aismallbizguru-backups
```

Set:

```env
LABBOX_SITE_HOST=lab.aismallbizguru.com
BASE_URL=https://lab.aismallbizguru.com
R2_BUCKET=lab-aismallbizguru-backups
R2_ENDPOINT=https://<account-id>.r2.cloudflarestorage.com
RESTIC_REPOSITORY=s3:https://<account-id>.r2.cloudflarestorage.com/lab-aismallbizguru-backups
```

For MinIO, use the same values for the app S3 credentials and root credentials unless you later add a narrower MinIO user:

```env
MINIO_ROOT_USER=<generated-user>
MINIO_ROOT_PASSWORD=<generated-password>
S3_ACCESS_KEY=<same-generated-user>
S3_SECRET_KEY=<same-generated-password>
```

## Runtime Directories

```bash
mkdir -p /opt/labbox/data/sqlite
mkdir -p /opt/labbox/data/minio
mkdir -p /opt/labbox/backup-staging
```

## Start

```bash
cd /opt/labbox
docker compose up -d --build
```

Check:

```bash
docker compose ps
curl https://lab.aismallbizguru.com/api/health
```

## First Backup

```bash
docker compose exec api bash /app/scripts/backup_now.sh
```

Then check backup status:

```bash
curl https://lab.aismallbizguru.com/api/health
```

## Never Commit Secrets

Before any commit:

```bash
git status --short
```

`.env`, SQLite files, MinIO data, and backup staging files must not appear as staged changes.
