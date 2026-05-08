# LabBox Deploy and Test Runbook

This is the operational runbook for another agent deploying this repo to the live VPS.

Production host:

```text
https://lab.aismallbizguru.com
```

VPS SSH target:

```text
root@lab.aismallbizguru.com
```

Deployment directory:

```text
/opt/labbox
```

Do not print or commit secrets. The production `.env` lives only on the VPS at `/opt/labbox/.env`.

## Local Preflight

From the repo root:

```bash
git status --short
LABBOX_ENV_FILE=.env.example docker compose config
```

From the backend directory:

```bash
cd backend
uv run pytest
uv run ruff check .
```

Expected current baseline:

```text
31 passed
All checks passed!
```

## Files That Must Stay Out of Git

Before committing or syncing, confirm these are not staged:

```text
.env
data/
backup-staging/
*.db
*.db-shm
*.db-wal
```

Use:

```bash
git status --short
```

## First-Time VPS Setup

For a fresh Debian/Ubuntu VPS:

```bash
ssh root@lab.aismallbizguru.com
sudo bash /opt/labbox/scripts/vps_setup.sh
mkdir -p /opt/labbox/data/sqlite /opt/labbox/data/minio /opt/labbox/backup-staging
```

The repo should be deployed to `/opt/labbox`.

## Sync Code to VPS

For normal deploys from local repo root:

```bash
rsync -av \
  --exclude .git \
  --exclude .venv \
  --exclude __pycache__ \
  --exclude .pytest_cache \
  --exclude .ruff_cache \
  --exclude data \
  --exclude backup-staging \
  --exclude .env \
  ./ root@lab.aismallbizguru.com:/opt/labbox/
```

For small targeted deploys, prefer `rsync -avR` so paths stay correct:

```bash
rsync -avR backend/app/main.py backend/app/settings.py root@lab.aismallbizguru.com:/opt/labbox/
```

Be careful not to copy files into the wrong directory. If a targeted `rsync` accidentally lands files under the wrong path, remove only those misplaced copies after confirming the correct files exist.

## Production Environment

Production env file:

```text
/opt/labbox/.env
```

Permissions:

```bash
chmod 600 /opt/labbox/.env
```

Required production host values:

```env
LABBOX_SITE_HOST=lab.aismallbizguru.com
BASE_URL=https://lab.aismallbizguru.com
CORS_ALLOW_ORIGINS=https://hmarquardt.github.io
SQLITE_PATH=/data/sqlite/labbox.db
APP_CONFIG_PATH=/config/apps.yaml
MINIO_AUTO_INIT=true
STORAGE_HEALTH_ENABLED=true
```

If the admin password was generated during bootstrap, the initial password is stored on the VPS:

```text
/root/labbox_initial_admin_password.txt
```

Do not print it unless the user explicitly asks.

## Rebuild and Restart

For backend changes:

```bash
ssh root@lab.aismallbizguru.com 'cd /opt/labbox && docker compose up -d --build api worker'
```

For Caddy config changes:

```bash
ssh root@lab.aismallbizguru.com 'cd /opt/labbox && docker compose up -d --force-recreate caddy'
```

For full stack:

```bash
ssh root@lab.aismallbizguru.com 'cd /opt/labbox && docker compose up -d --build'
```

Check container state:

```bash
ssh root@lab.aismallbizguru.com 'cd /opt/labbox && docker compose ps'
```

## Smoke Tests

Public health:

```bash
curl -sS https://lab.aismallbizguru.com/api/health
```

Expected shape:

```json
{"status":"ok","version":"0.1.0","host":"lab.aismallbizguru.com","db":"ok","storage":"ok"}
```

Root redirect:

```bash
curl -i -sS https://lab.aismallbizguru.com/
```

Expected:

```text
HTTP/2 302
location: /admin/login
```

Admin login page:

```bash
curl -i -sS https://lab.aismallbizguru.com/admin/login
```

Expected:

```text
HTTP/2 200
```

GitHub Pages CORS preflight:

```bash
curl -i -sS -X OPTIONS https://lab.aismallbizguru.com/api/apps \
  -H 'Origin: https://hmarquardt.github.io' \
  -H 'Access-Control-Request-Method: GET'
```

Expected headers:

```text
access-control-allow-origin: https://hmarquardt.github.io
access-control-allow-methods: GET, POST, PATCH, DELETE, OPTIONS
```

Private resources should still reject unauthenticated reads unless configured public:

```bash
curl -i -sS https://lab.aismallbizguru.com/api/junk-drawer/notes \
  -H 'Origin: https://hmarquardt.github.io'
```

Expected:

```text
HTTP/2 401
```

## Public Read Setup for Static Sites

For a GitHub Pages frontend to read without a proxy:

1. Add the GitHub Pages origin to `CORS_ALLOW_ORIGINS`.
2. Set the app config to public read:

```yaml
auth:
  default_read: public
  default_write: token
```

3. Restart the API and worker:

```bash
ssh root@lab.aismallbizguru.com 'cd /opt/labbox && docker compose up -d --build api worker'
```

Writes remain bearer-token protected.

## Admin Smoke Test Without Printing Secrets

To check authenticated admin pages from the VPS without exposing the session secret:

```bash
ssh root@lab.aismallbizguru.com 'cd /opt/labbox && SESSION=$(grep "^ADMIN_SESSION_SECRET=" .env | cut -d= -f2-) && curl -sS -o /tmp/admin_apps.html -w "%{http_code}" -H "Cookie: session=$SESSION" https://lab.aismallbizguru.com/admin/apps'
```

Expected:

```text
200
```

Resource browser smoke test:

```bash
ssh root@lab.aismallbizguru.com 'cd /opt/labbox && SESSION=$(grep "^ADMIN_SESSION_SECRET=" .env | cut -d= -f2-) && curl -sS -o /tmp/admin_resource.html -w "%{http_code}" -H "Cookie: session=$SESSION" https://lab.aismallbizguru.com/admin/apps/junk-drawer/notes'
```

Expected:

```text
200
```

Confirm rendered links:

```bash
ssh root@lab.aismallbizguru.com 'grep -q "/admin/apps/junk-drawer/notes" /tmp/admin_apps.html && grep -q "New Record" /tmp/admin_resource.html && echo ok'
```

Expected:

```text
ok
```

## Logs

Recent API and Caddy logs:

```bash
ssh root@lab.aismallbizguru.com 'cd /opt/labbox && docker compose logs --tail=120 api caddy'
```

All services:

```bash
ssh root@lab.aismallbizguru.com 'cd /opt/labbox && docker compose logs --tail=120'
```

## Commit and Push

After successful local checks and deploy smoke tests:

```bash
git status --short
git add <changed-files>
git commit -m "<short imperative message>"
git push
```

Never stage `/opt/labbox/.env`, local `.env`, SQLite data, MinIO data, or backup staging files.
