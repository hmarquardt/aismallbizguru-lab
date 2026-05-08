# PRD: LabBox Backend

## 1. Product Summary

Build a lightweight, reusable backend appliance for personal experiments and small private web tools.

The system will run on the Hetzner VPS currently available at:

**https://lab.aismallbizguru.com**

LabBox Backend is intended to support web projects that are more ambitious than single-page local-first apps, but are **not production SaaS systems with paying customers**.

The system provides:

- Python API
- SQLite database
- MinIO S3-compatible local object storage
- Cloudflare R2 remote backups
- Bearer token API access
- Admin access via hashed password stored in `.env`
- Config-driven app/resource definitions where practical
- Docker Compose development and deployment

The goal is to make new experiments easier to launch by changing config rather than writing a new backend from scratch each time.

---

## 2. Working Name

**LabBox Backend**

Alternative names considered:

- Junk Drawer Backend
- Experiment Appliance
- HankStack
- Tinkerbase
- LocalLab Server

For this PRD, the product name is **LabBox Backend**.

---

## 3. Production Host

Primary deployment host:

| Item | Value |
|---|---|
| Domain | `lab.aismallbizguru.com` |
| Provider | Hetzner |
| Deployment style | Docker Compose on VPS |
| Public URL | `https://lab.aismallbizguru.com` |

The base domain will serve the LabBox admin interface and API gateway.

Optional future subdomains:

- `api.lab.aismallbizguru.com`
- `minio.lab.aismallbizguru.com`
- `admin.lab.aismallbizguru.com`

For MVP, prefer keeping everything under:

```text
https://lab.aismallbizguru.com
```

with path-based routing.

---

## 4. Problem Statement

The user has built many one-page, local-first web apps. These are fast to build and easy to deploy, but they hit limits when they need:

- Durable shared storage
- File uploads
- Private admin access
- Cross-device sync
- Simple APIs
- Lightweight authentication
- Recurring jobs
- Remote backups
- Reusable backend patterns

Building a new custom backend for each experiment adds too much friction.

LabBox Backend solves this by providing a small reusable backend layer for experimental tools.

---

## 5. Target User

Primary user:

> A technical solo builder running personal experiments, prototypes, dashboards, utilities, creative tools, and small private web apps.

Secondary users:

- Trusted friends/testers
- Private collaborators
- Small community tools
- Admin-only dashboards

This is **not** intended for:

- Public SaaS
- Regulated data
- High-concurrency apps
- Formal customer production systems
- Complex multi-tenant commercial systems

---

## 6. Goals

### 6.1 Core Goals

LabBox Backend should:

- Run cheaply on the Hetzner VPS
- Be available at `lab.aismallbizguru.com`
- Be easy to develop locally with Docker
- Deploy with Docker Compose
- Expose a simple Python API
- Use SQLite as the primary database
- Use MinIO for local S3-compatible object storage
- Back up database, config, and uploaded files to Cloudflare R2
- Support multiple small apps from one backend
- Allow new resources to be defined through config
- Support bearer token access
- Support admin login via password hash stored in `.env`
- Provide a simple admin UI

### 6.2 Design Goals

The system should be:

- Boring
- Inspectable
- Cheap
- Easy to rebuild
- Easy to back up
- Easy to restore
- Easy to extend with small Python modules

### 6.3 Non-Goals

LabBox Backend should **not** try to be:

- Firebase
- Supabase
- Airtable
- A complete no-code platform
- A Kubernetes system
- A horizontally scalable backend
- A formal multi-tenant SaaS foundation
- A complete identity provider
- An enterprise backup platform

---

## 7. Deployment Assumption

Current VPS:

| Item | Value |
|---|---|
| Provider | Hetzner |
| Domain | `lab.aismallbizguru.com` |
| OS | Ubuntu 24.04 LTS or Debian 12 preferred |
| Deployment | Docker Compose |
| Reverse Proxy | Caddy |
| TLS | Automatic HTTPS via Caddy |

Expected services:

| Service | Purpose |
|---|---|
| `caddy` | Reverse proxy and HTTPS |
| `api` | FastAPI backend |
| `worker` | Background jobs and backup orchestration |
| `minio` | Local S3-compatible object storage |
| `backup` | Restic backups to Cloudflare R2 |

---

## 8. Architecture Overview

```text
Browser / Static App
        |
        | HTTPS
        v
lab.aismallbizguru.com
        |
        v
Caddy Reverse Proxy
        |
        v
FastAPI Backend
        |
        +--> SQLite database
        |
        +--> MinIO local object storage
        |
        +--> Config files
        |
        +--> Worker process
                  |
                  +--> Backup staging
                  |
                  +--> Restic
                            |
                            v
                    Cloudflare R2 bucket
```

---

## 9. Public URL Structure

MVP should use path-based routing.

| URL | Purpose |
|---|---|
| `https://lab.aismallbizguru.com/` | Landing page or admin redirect |
| `https://lab.aismallbizguru.com/admin` | Admin UI |
| `https://lab.aismallbizguru.com/api` | API root |
| `https://lab.aismallbizguru.com/api/health` | Health check |
| `https://lab.aismallbizguru.com/files` | Proxied file access |

MinIO should not be publicly exposed by default.

Internal-only service names:

```text
http://api:8000
http://minio:9000
```

Optional private MinIO console:

```text
http://minio:9001
```

If exposed later, the MinIO console should be protected separately.

---

## 10. Core Components

### 10.1 FastAPI Backend

The backend exposes APIs for:

- Health checks
- Authentication
- App registry
- Generic resources
- File uploads
- File downloads
- Admin operations
- Backup status
- Event logs

Preferred stack:

- Python 3.12+
- FastAPI
- Pydantic
- SQLAlchemy or SQLModel
- SQLite
- `boto3` or `minio-py`
- APScheduler or simple worker loop

---

### 10.2 SQLite Database

SQLite is the primary database.

Expected usage:

- Modest traffic
- Single VPS
- Low to moderate writes
- Many tiny apps
- Personal/private data
- Experimental tools

SQLite should be configured with:

```sql
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA foreign_keys=ON;
PRAGMA busy_timeout=5000;
```

The system should avoid long-running write transactions.

---

### 10.3 MinIO Local Object Storage

MinIO will run on the same Hetzner VPS and provide local S3-compatible storage for uploaded assets.

Uses:

- Uploaded images
- Audio files
- JSON exports
- Generated files
- App-specific blobs

MinIO is acceptable on the same VPS because this system is for experiments, not formal production workloads.

Important distinction:

> MinIO is local object storage. Cloudflare R2 is remote backup.

MinIO data must be included in the remote backup plan.

---

### 10.4 Cloudflare R2 Remote Backup

Cloudflare R2 will be the off-box backup destination.

Backups will be encrypted before upload using Restic.

Backup target:

```text
Cloudflare R2 bucket
```

Suggested bucket names:

- `labbox-backups`
- `smallbizguru-labbox-backups`
- `lab-aismallbizguru-backups`

Recommended final bucket name:

```text
lab-aismallbizguru-backups
```

---

## 11. Data Model

### 11.1 Recommended Initial Schema

Use a flexible record model rather than generating one SQL table per experiment.

```sql
CREATE TABLE apps (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT,
  config_version TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE records (
  id TEXT PRIMARY KEY,
  app_id TEXT NOT NULL,
  resource TEXT NOT NULL,
  data_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  deleted_at TEXT,
  FOREIGN KEY(app_id) REFERENCES apps(id)
);

CREATE TABLE files (
  id TEXT PRIMARY KEY,
  app_id TEXT NOT NULL,
  resource TEXT,
  record_id TEXT,
  bucket TEXT NOT NULL,
  object_key TEXT NOT NULL,
  filename TEXT NOT NULL,
  content_type TEXT,
  size_bytes INTEGER,
  checksum TEXT,
  created_at TEXT NOT NULL,
  deleted_at TEXT,
  FOREIGN KEY(app_id) REFERENCES apps(id)
);

CREATE TABLE api_tokens (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  token_hash TEXT NOT NULL,
  scopes_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  expires_at TEXT,
  revoked_at TEXT
);

CREATE TABLE events (
  id TEXT PRIMARY KEY,
  app_id TEXT,
  actor TEXT,
  action TEXT NOT NULL,
  resource TEXT,
  record_id TEXT,
  metadata_json TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE jobs (
  id TEXT PRIMARY KEY,
  app_id TEXT,
  job_type TEXT NOT NULL,
  payload_json TEXT,
  status TEXT NOT NULL,
  run_after TEXT,
  attempts INTEGER NOT NULL DEFAULT 0,
  last_error TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE backup_runs (
  id TEXT PRIMARY KEY,
  status TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  destination TEXT NOT NULL,
  snapshot_id TEXT,
  bytes_added INTEGER,
  error TEXT
);
```

---

### 11.2 Why JSON Records?

This keeps the system flexible.

Instead of creating migrations for every tiny app idea, records can store structured JSON:

```json
{
  "title": "Snake Habitat Route",
  "notes": "Good road-cruising candidate after rain",
  "lat": 38.35,
  "lng": -87.57,
  "tags": ["wildlife", "map", "field"]
}
```

Config defines validation and display behavior, not necessarily the physical SQL shape.

---

## 12. Configuration System

### 12.1 App Config

Each experiment can be defined in YAML.

Example:

```yaml
apps:
  snake-routes:
    title: Snake Route Explorer
    description: Local herping route planner
    auth:
      default_read: private
      default_write: token
    resources:
      routes:
        label: Routes
        fields:
          title:
            type: string
            required: true
          notes:
            type: text
          waypoints:
            type: json
          tags:
            type: list
        files:
          enabled: true
          allowed_types:
            - image/png
            - image/jpeg
            - application/json
```

---

### 12.2 Config Should Handle

- App names
- Resources
- Field definitions
- Required fields
- Allowed file types
- Max file size
- Basic permissions
- Display labels
- Public/private resource defaults
- Token scopes

### 12.3 Config Should Not Handle Yet

- Complex workflows
- Custom business logic
- Advanced permissions
- Multi-step automations
- Payments
- Tenant isolation
- Full UI generation

When the app becomes weird, write Python.

---

## 13. API Requirements

### 13.1 Health

```http
GET /api/health
```

Returns:

```json
{
  "status": "ok",
  "version": "0.1.0",
  "db": "ok",
  "storage": "ok",
  "host": "lab.aismallbizguru.com"
}
```

---

### 13.2 App Registry

```http
GET /api/apps
GET /api/apps/{app_id}
```

Returns available apps and resource definitions visible to the current token.

---

### 13.3 Generic Resource API

```http
GET    /api/{app_id}/{resource}
POST   /api/{app_id}/{resource}
GET    /api/{app_id}/{resource}/{record_id}
PATCH  /api/{app_id}/{resource}/{record_id}
DELETE /api/{app_id}/{resource}/{record_id}
```

Soft delete by default.

---

### 13.4 File API

```http
POST   /api/{app_id}/{resource}/{record_id}/files
GET    /api/{app_id}/{resource}/{record_id}/files
GET    /api/files/{file_id}
DELETE /api/files/{file_id}
```

For v1, files can be proxied through the API.

Later enhancement:

- Signed upload URLs
- Signed download URLs

---

### 13.5 Admin API

```http
POST /admin/login
GET  /admin/status
GET  /admin/apps
GET  /admin/events
GET  /admin/backups
POST /admin/backups/run
POST /admin/tokens
POST /admin/tokens/{id}/revoke
```

---

## 14. Authentication and Authorization

### 14.1 Admin Login

Admin login uses a password hash stored in `.env`.

```env
ADMIN_PASSWORD_HASH=$argon2id$...
ADMIN_SESSION_SECRET=...
```

Requirements:

- Raw admin password must never be stored
- Use Argon2id or bcrypt
- Login creates an HTTP-only secure session cookie
- Admin session expires after configurable duration

---

### 14.2 Bearer Tokens

API clients use bearer tokens.

```http
Authorization: Bearer <token>
```

Tokens are stored hashed in SQLite.

Token scopes example:

```json
{
  "apps": {
    "snake-routes": ["read", "write", "files"],
    "junk-drawer": ["read"]
  },
  "admin": false
}
```

Requirements:

- Tokens shown only once at creation
- Store only token hash
- Support revocation
- Support optional expiration
- Support app-level scopes

---

## 15. Admin UI Requirements

The admin UI can be plain, boring, and useful.

Required screens:

- Login
- Dashboard
- Apps list
- Resource browser
- Record viewer/editor
- File browser
- Token manager
- Backup status
- Manual backup trigger
- Recent events/errors
- Config viewer

The admin UI should not require a separate frontend build pipeline in v1.

Acceptable approaches:

- FastAPI + Jinja templates
- Small static admin SPA served by FastAPI

---

## 16. Backup Requirements

### 16.1 Backup Destination

Remote backup target:

```text
Cloudflare R2 bucket
```

Recommended bucket name:

```text
lab-aismallbizguru-backups
```

---

### 16.2 Backup Tool

Use:

```text
restic
```

Why:

- Encrypted backups
- Deduplication
- Snapshots
- Retention policies
- Supports S3-compatible backends
- Easy restore testing

Optional helper:

```text
rclone
```

Use rclone only if needed for manual inspection or bucket-to-bucket movement.

---

### 16.3 What Gets Backed Up

Backup set:

```text
/opt/labbox/config/
/opt/labbox/data/sqlite/
/opt/labbox/data/minio/
/opt/labbox/docker-compose.yml
/opt/labbox/Caddyfile
```

Sensitive files:

```text
/opt/labbox/.env
```

The `.env` file should either be:

- Included in encrypted Restic backup, or
- Backed up separately in a password manager or encrypted notes system

---

### 16.4 SQLite Backup Safety

Do not rely on copying a hot SQLite database file directly.

Preferred v1 approach:

1. Use SQLite backup command to create a consistent backup file.
2. Place that file in backup staging.
3. Restic backs up the staging file.

Example flow:

```bash
sqlite3 /data/sqlite/labbox.db ".backup '/backup-staging/labbox.db'"
```

Backup should include:

- SQLite backup copy
- MinIO object data
- Config files
- Deployment files

---

### 16.5 Backup Frequency

Default schedule:

```text
Nightly backup at 3:30 AM server time
```

Optional manual backup:

```text
Admin UI -> Run Backup Now
```

---

### 16.6 Retention Policy

Default Restic retention:

- Keep 7 daily
- Keep 4 weekly
- Keep 6 monthly

Command shape:

```bash
restic forget --keep-daily 7 --keep-weekly 4 --keep-monthly 6 --prune
```

---

### 16.7 Backup Verification

Requirements:

- Backup job records success/failure in `backup_runs`
- Admin dashboard shows last successful backup
- Admin dashboard warns if no successful backup in 48 hours
- Weekly `restic check` job
- Monthly restore test documented

Minimum viable restore test:

1. Create temporary restore directory.
2. Restore latest snapshot.
3. Verify SQLite backup file exists.
4. Verify MinIO data exists.
5. Optionally launch local Compose stack against restored data.

---

## 17. Environment Variables

Example `.env`:

```env
APP_ENV=production
BASE_URL=https://lab.aismallbizguru.com
TZ=America/Indiana/Indianapolis

ADMIN_PASSWORD_HASH=
ADMIN_SESSION_SECRET=

API_TOKEN_PEPPER=

SQLITE_PATH=/data/sqlite/labbox.db

MINIO_ROOT_USER=
MINIO_ROOT_PASSWORD=
MINIO_BUCKET=labbox-assets
S3_ENDPOINT=http://minio:9000
S3_ACCESS_KEY=
S3_SECRET_KEY=
S3_REGION=us-east-1

R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET=lab-aismallbizguru-backups
R2_ENDPOINT=https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com

RESTIC_REPOSITORY=s3:https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com/lab-aismallbizguru-backups
RESTIC_PASSWORD=

BACKUP_RETENTION_DAILY=7
BACKUP_RETENTION_WEEKLY=4
BACKUP_RETENTION_MONTHLY=6
```

---

## 18. Docker Compose Requirements

Required containers:

| Container | Purpose |
|---|---|
| `caddy` | HTTPS reverse proxy |
| `api` | FastAPI backend |
| `worker` | Background jobs |
| `minio` | Local object storage |
| `backup` | Restic backup runner |

Nice-to-have:

| Container | Purpose |
|---|---|
| `watchtower` | Optional updates; disabled by default |

Suggested volume layout:

```text
/opt/labbox/
  docker-compose.yml
  Caddyfile
  .env
  config/
    apps.yaml
  data/
    sqlite/
    minio/
    caddy/
    logs/
    backup-staging/
```

---

## 19. Security Requirements

Appropriate security for personal experiments:

- SSH keys only
- Disable password SSH
- Firewall allows only 22, 80, 443
- Caddy handles HTTPS
- MinIO API not publicly exposed
- MinIO console not publicly exposed by default
- Admin login over HTTPS only
- Admin cookie is HTTP-only and secure
- Bearer tokens stored hashed
- Backups encrypted before leaving VPS

Out of scope:

- OAuth
- SSO
- Complex RBAC
- Audit compliance
- Tenant isolation guarantees

---

## 20. Observability Requirements

Minimum:

- Structured application logs
- Recent error log in admin UI
- Backup run history
- Health endpoint
- Storage connectivity check
- SQLite connectivity check

Admin dashboard should show:

- App version
- Uptime
- Database size
- MinIO storage usage if available
- Last backup status
- Last backup time
- Number of apps
- Number of records
- Number of files

---

## 21. MVP Scope

### 21.1 MVP Must Have

- Docker Compose dev environment
- FastAPI backend
- SQLite with WAL mode
- MinIO local object storage
- Cloudflare R2 Restic backup
- Admin password hash login
- Bearer token auth
- Config-defined apps/resources
- Generic CRUD API
- Basic file upload API
- Simple admin UI
- Nightly backup job
- Manual backup trigger
- Restore instructions

### 21.2 MVP Should Have

- Event log
- Token scopes
- Backup status dashboard
- Config validation at startup
- Export app data as JSON
- Soft delete records

### 21.3 MVP Could Have

- CSV export
- Signed download URLs
- File previews
- Simple webhook support
- Scheduled jobs per app
- Per-app public/private flags

---

## 22. Future Enhancements

- Signed upload URLs
- Per-app static frontend hosting
- Automatic schema/index suggestions
- Webhook receiver framework
- Lightweight cron/job config
- App templates
- OpenAI-compatible LLM task runner
- Browser local-first sync helper library
- Import/export ZIP bundles
- Optional Postgres adapter
- Optional direct R2 object storage instead of local MinIO
- Simple generated admin forms from config

---

## 23. Acceptance Criteria

MVP is complete when:

1. LabBox is running at `https://lab.aismallbizguru.com`.
2. A new app can be added through YAML config.
3. The API exposes CRUD endpoints for that app’s resources.
4. A browser app can authenticate with a bearer token.
5. Records are stored in SQLite.
6. Files are uploaded to MinIO.
7. Admin can log in with password.
8. Admin can view apps, records, files, tokens, and backup status.
9. A nightly backup runs to Cloudflare R2.
10. Backups are encrypted before leaving the VPS.
11. A manual backup can be triggered.
12. A documented restore process successfully restores SQLite and MinIO data.
13. The whole system runs under Docker Compose on the Hetzner VPS.

---

## 24. Suggested Build Milestones

### Milestone 1: Skeleton

- Repo structure
- Docker Compose
- FastAPI hello world
- Caddy reverse proxy
- SQLite connection
- Health endpoint
- Public availability at `https://lab.aismallbizguru.com/api/health`

### Milestone 2: Config Registry

- Load `apps.yaml`
- Validate config
- Expose app registry API
- Startup failure on invalid config

### Milestone 3: Generic Records

- Records table
- CRUD endpoints
- JSON validation against config
- Soft delete

### Milestone 4: Auth

- Admin password hash verification
- Admin session cookie
- Bearer token creation
- Token hash storage
- Token scopes

### Milestone 5: Files

- MinIO container
- Bucket initialization
- File upload endpoint
- File metadata table
- File download endpoint

### Milestone 6: Admin UI

- Login
- Dashboard
- Apps/resources
- Records browser
- File browser
- Token manager

### Milestone 7: Cloudflare R2 Backup

- Restic container
- R2 credential config
- SQLite consistent backup step
- MinIO data backup
- Nightly schedule
- Manual backup trigger
- `backup_runs` table

### Milestone 8: Restore and Hardening

- Restore documentation
- Test restore locally
- Firewall notes
- Production Compose profile
- Log rotation
- Backup warning in admin UI

---

## 25. Implementation Notes

### 25.1 Recommended Repo Structure

```text
labbox-backend/
  README.md
  docker-compose.yml
  docker-compose.dev.yml
  Caddyfile
  .env.example

  backend/
    pyproject.toml
    app/
      main.py
      config/
      auth/
      db/
      records/
      files/
      admin/
      backups/
      jobs/

  config/
    apps.yaml

  scripts/
    init_minio.sh
    backup_now.sh
    restore_latest.sh
    create_admin_hash.py
    create_token.py

  docs/
    deployment.md
    backup-restore.md
    app-config.md
```

---

### 25.2 Example Backup Flow

1. Worker receives scheduled backup event.
2. Worker creates `backup_runs` row with `status = running`.
3. Worker runs SQLite `.backup` into `/backup-staging`.
4. Worker calls Restic backup against:
   - Config
   - Backup-staging SQLite copy
   - MinIO data
   - Deployment files
5. Worker runs Restic forget/prune based on retention config.
6. Worker updates `backup_runs` with success/failure and snapshot ID.
7. Admin dashboard displays result.

---

## 26. Development Philosophy

LabBox Backend should remain small and practical.

The system should not become a generic no-code platform. Config should make common cases easy, but custom Python should remain acceptable and expected for weird experiments.

Preferred principle:

> Config-assisted, not config-magical.

When a new experiment needs something ordinary, use config.

When a new experiment needs something strange, write code.

---

## 27. Final Product Principle

LabBox Backend should be:

- Small enough to understand
- Boring enough to trust
- Cheap enough to leave running
- Flexible enough for weird experiments
- Simple enough to rebuild from scratch

The correct success metric is not “enterprise-ready.”

The success metric is:

> I had a new experiment idea at 10 AM, added a resource config, dropped a static frontend on GitHub Pages, and by lunch it had storage, uploads, auth, and backups.
