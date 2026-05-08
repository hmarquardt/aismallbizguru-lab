# LabBox Backend: Process Task Document

## Purpose

This document turns the LabBox Backend PRD into an implementation process.

The repository directory already exists. Git has already been initialized, and a remote GitHub repository is already associated.

The intended workflow is:

- **Codex / Opencode** will be launched from the existing project directory.
- **Codex / Opencode** handles setup, integration, deployment, Docker, VPS configuration, and final orchestration.
- **MiniMax 2.7** handles small, focused coding tasks.
- Tasks should be completed in order where possible.
- Each task should be small enough to hand to a coding model without requiring it to understand the entire project history.

Primary deployment target:

```text
https://labs.smallbizguru.com
```

Primary stack:

```text
Python
FastAPI
SQLite
MinIO
Cloudflare R2
Restic
Caddy
Docker Compose
Hetzner VPS
```

---

# 1. Critical Repository and Secret Rules

## 1.1 Existing Repo Assumption

The project is already in the current working directory.

Agents should **not** create a new parent project directory.

Do not do this:

```bash
mkdir labbox-backend
cd labbox-backend
git init
```

Instead, assume:

```bash
pwd
```

is already the project root.

Agents may create files and subdirectories inside the current directory as needed.

---

## 1.2 Git Rules

The repository already has Git initialized and a remote configured.

Agents should not reinitialize Git.

Do not run:

```bash
git init
git remote add origin ...
```

Agents may run read-only Git inspection commands:

```bash
git status
git remote -v
git branch
```

Agents may stage/commit only if explicitly asked.

---

## 1.3 Secret Handling Rules

This is mandatory.

The real `.env` file must **never** be committed to Git.

The `.gitignore` file must include:

```gitignore
.env
.env.*
!.env.example
```

Exception:

```text
.env.example is allowed and encouraged.
```

`.env.example` must contain placeholders only.

No real secrets may appear in:

- Git-tracked files
- README
- docs
- shell history examples
- test fixtures
- Docker Compose files
- screenshots
- generated logs

---

## 1.4 Required Secret Categories

Deployment requires secrets and credentials that must be created or supplied during the deploy process.

Secrets include:

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

These belong in the real server-side `.env` file only.

---

## 1.5 Deploy-Time Secret Process

The deploy process must explicitly include a secrets step.

Deployment documentation must include:

1. Copy `.env.example` to `.env`.
2. Generate an admin password hash.
3. Generate `ADMIN_SESSION_SECRET`.
4. Generate `API_TOKEN_PEPPER`.
5. Generate MinIO credentials.
6. Create Cloudflare R2 bucket.
7. Create Cloudflare R2 access keys.
8. Generate `RESTIC_PASSWORD`.
9. Fill in `.env` on the VPS.
10. Confirm `.env` is ignored by Git.
11. Start Docker Compose.
12. Run the first backup test.

Before any commit, agents should verify:

```bash
git status --short
```

and confirm `.env` is not staged.

---

# 2. Working Rules for AI Coding Agents

## 2.1 Codex / Opencode Role

Codex or Opencode should be used for:

- Working in the existing repo directory
- Inspecting the current project state
- Creating missing project structure inside the current directory
- Docker Compose setup
- VPS deployment
- Caddy configuration
- Environment file templates
- End-to-end integration
- Running tests
- Debugging deployment failures
- Reviewing MiniMax-produced code
- Applying patches
- Final assembly

Codex / Opencode should maintain project coherence.

Codex / Opencode may modify multiple files when needed.

Codex / Opencode must preserve the existing Git repo and remote configuration.

---

## 2.2 MiniMax 2.7 Role

MiniMax 2.7 should be used for:

- Small isolated Python modules
- API route files
- Pydantic models
- SQLAlchemy/SQLModel models
- Utility scripts
- Jinja templates
- Tests for specific modules
- Single-purpose shell scripts
- Small documentation files

MiniMax tasks should be:

- Narrow
- Explicit
- File-targeted
- Testable
- Given with clear acceptance criteria

MiniMax should not be asked to redesign the architecture unless explicitly requested.

MiniMax should not be asked to perform VPS deployment.

---

## 2.3 General Implementation Rules

All implementation should follow these rules:

- Work in the existing current directory.
- Do not create a new high-level project folder.
- Do not run `git init`.
- Do not add or change Git remotes.
- Prefer boring code over clever abstractions.
- Keep modules small.
- Use type hints.
- Use environment variables for secrets.
- Never commit real secrets.
- Keep `.env.example` complete but secret-free.
- Ensure `.env` is ignored by Git.
- Use SQLite WAL mode.
- Use soft deletes where specified.
- Keep MinIO internal by default.
- Backups must be encrypted before leaving the VPS.
- Config should assist common use cases but not become a full no-code platform.
- When an app needs weird behavior, custom Python modules are allowed.

---

# 3. Target Repo Structure

The current directory should become this structure.

Do not create an extra wrapper directory.

```text
./
  README.md
  docker-compose.yml
  docker-compose.dev.yml
  Caddyfile
  .env.example
  .gitignore

  backend/
    pyproject.toml
    Dockerfile
    app/
      __init__.py
      main.py
      settings.py

      config/
        __init__.py
        loader.py
        models.py
        routes.py

      db/
        __init__.py
        session.py
        models.py
        init_db.py

      auth/
        __init__.py
        password.py
        tokens.py
        dependencies.py
        routes.py

      records/
        __init__.py
        schemas.py
        service.py
        routes.py

      files/
        __init__.py
        storage.py
        schemas.py
        service.py
        routes.py

      admin/
        __init__.py
        routes.py
        templates/
          base.html
          login.html
          dashboard.html
          apps.html
          records.html
          files.html
          tokens.html
          backups.html

      backups/
        __init__.py
        service.py
        routes.py

      jobs/
        __init__.py
        worker.py

      events/
        __init__.py
        service.py

      health/
        __init__.py
        routes.py

      static/
        admin.css

    tests/
      test_health.py
      test_config_loader.py
      test_records.py
      test_auth.py
      test_files.py

  config/
    apps.yaml

  scripts/
    init_minio.sh
    backup_now.sh
    restore_latest.sh
    create_admin_hash.py
    create_token.py
    vps_setup.sh

  docs/
    deployment.md
    backup-restore.md
    app-config.md
    api-examples.md
```

---

# 4. Implementation Phases

## Phase 0: Existing Repo Audit and Local Foundation

Goal:

Inspect the existing project directory, confirm Git remote, add missing base files, create Docker environment, Python package, and initial FastAPI health check.

Primary agent:

```text
Codex / Opencode
```

MiniMax may be used for small files after the base structure exists.

---

## Phase 1: Config Registry

Goal:

Load and validate app/resource definitions from YAML.

Primary agent:

```text
MiniMax 2.7
```

Codex / Opencode reviews and integrates.

---

## Phase 2: SQLite Data Layer

Goal:

Create SQLite connection, tables, WAL configuration, and basic DB lifecycle.

Primary agent:

```text
MiniMax 2.7
```

Codex / Opencode reviews and integrates.

---

## Phase 3: Generic Records API

Goal:

Provide CRUD endpoints for config-defined app resources.

Primary agent:

```text
MiniMax 2.7
```

Codex / Opencode handles integration testing.

---

## Phase 4: Auth

Goal:

Admin password verification, bearer token creation, token hashing, token scopes.

Primary agent:

```text
MiniMax 2.7
```

Codex / Opencode handles end-to-end auth testing.

---

## Phase 5: MinIO File Storage

Goal:

Upload files to MinIO, store metadata in SQLite, download files through API.

Primary agent:

```text
MiniMax 2.7
```

Codex / Opencode handles Docker MinIO integration.

---

## Phase 6: Admin UI

Goal:

Simple Jinja-based admin interface for visibility and management.

Primary agent:

```text
MiniMax 2.7
```

Codex / Opencode integrates routes and templates.

---

## Phase 7: Cloudflare R2 Backups

Goal:

Encrypted Restic backups to Cloudflare R2, backup status tracking, manual trigger.

Primary agent:

```text
Codex / Opencode for setup and orchestration
MiniMax for Python backup status/service code
```

---

## Phase 8: VPS Deployment

Goal:

Deploy to Hetzner VPS at `labs.smallbizguru.com`.

Primary agent:

```text
Codex / Opencode
```

---

# 5. Ordered Todo List

## 5.1 Foundation Tasks

### TODO 001: Audit Existing Repository

Agent:

```text
Codex / Opencode
```

Task:

Inspect the existing current directory before creating files.

Commands allowed:

```bash
pwd
ls -la
git status
git remote -v
find . -maxdepth 2 -type f | sort
```

Requirements:

- Confirm current directory is the project root.
- Confirm Git remote exists.
- Identify existing files.
- Do not create a new wrapper directory.
- Do not run `git init`.
- Do not change Git remote.

Acceptance Criteria:

- Agent reports current repo state.
- Agent identifies files that already exist.
- Agent confirms `.env` is not tracked.
- Agent proceeds using the existing directory.

---

### TODO 002: Create or Update `.gitignore`

Agent:

```text
Codex / Opencode
```

Target file:

```text
.gitignore
```

Task:

Create or update `.gitignore`.

Required entries:

```gitignore
# Secrets
.env
.env.*
!.env.example

# Python
__pycache__/
*.py[cod]
.pytest_cache/
.mypy_cache/
.ruff_cache/
.venv/
venv/

# SQLite
*.db
*.db-shm
*.db-wal
data/sqlite/
backup-staging/

# Docker/local data
data/
docker-data/
.minio/

# OS/editor
.DS_Store
Thumbs.db
.idea/
.vscode/
```

Acceptance Criteria:

- `.env` and `.env.*` are ignored.
- `.env.example` is not ignored.
- SQLite database files are ignored.
- Local data directories are ignored.
- `git status --short` does not show `.env`.

---

### TODO 003: Create Base Project Files

Agent:

```text
Codex / Opencode
```

Task:

Create missing base files in the current directory.

Target files:

```text
README.md
.env.example
Caddyfile
docker-compose.yml
docker-compose.dev.yml
config/apps.yaml
```

Requirements:

- Do not include real secrets.
- `.env.example` must contain all required placeholder values.
- `config/apps.yaml` should include a sample `junk-drawer` app.
- Caddyfile may be placeholder if API is not ready yet.

Acceptance Criteria:

- Files exist.
- No real secrets are present.
- Project root remains current directory.
- `.env.example` is safe to commit.

---

### TODO 004: Create Python Project Configuration

Agent:

```text
Codex / Opencode
```

Target file:

```text
backend/pyproject.toml
```

Task:

Create Python project configuration for FastAPI.

Use:

- Python 3.12+
- FastAPI
- Uvicorn
- Pydantic
- Pydantic Settings
- SQLAlchemy or SQLModel
- Jinja2
- Argon2 or bcrypt support
- PyYAML
- boto3 or minio
- pytest
- httpx

Acceptance Criteria:

- Dependencies install locally.
- `pytest` can run even before tests exist.
- Package layout supports importing `app.main`.

---

### TODO 005: Create FastAPI App Skeleton

Agent:

```text
MiniMax 2.7
```

Target files:

```text
backend/app/main.py
backend/app/settings.py
backend/app/health/routes.py
```

Task:

Create a FastAPI app with settings and a health endpoint.

Requirements:

- Load settings from environment.
- Define `APP_ENV`, `BASE_URL`, `SQLITE_PATH`.
- Add `GET /api/health`.
- Health endpoint returns app status, version, host, and placeholder DB/storage statuses.

Acceptance Criteria:

```http
GET /api/health
```

returns:

```json
{
  "status": "ok",
  "version": "0.1.0",
  "host": "labs.smallbizguru.com",
  "db": "unknown",
  "storage": "unknown"
}
```

---

### TODO 006: Create Backend Dockerfile

Agent:

```text
Codex / Opencode
```

Target file:

```text
backend/Dockerfile
```

Task:

Create a Dockerfile for the FastAPI backend.

Requirements:

- Use Python 3.12 slim image.
- Install project dependencies.
- Run app with Uvicorn.
- Expose port `8000`.
- Use `/app` as working directory.

Acceptance Criteria:

- Backend image builds.
- Container starts locally.
- Health endpoint is reachable inside Docker network.

---

### TODO 007: Create Docker Compose Development Stack

Agent:

```text
Codex / Opencode
```

Target files:

```text
docker-compose.dev.yml
.env.example
```

Task:

Create a local development Docker Compose stack.

Services:

- `api`
- `minio`

Requirements:

- API mounts backend source for development.
- MinIO stores data in local Docker volume.
- API can reach MinIO at `http://minio:9000`.
- Ports may be exposed locally for development.
- Real `.env` is not required for a basic local health check if placeholder defaults are safe.

Acceptance Criteria:

- `docker compose -f docker-compose.dev.yml up` starts API and MinIO.
- API health endpoint works locally.
- MinIO console is reachable locally only.
- No secrets are committed.

---

## 5.2 Config Registry Tasks

### TODO 008: Define App Config Schema

Agent:

```text
MiniMax 2.7
```

Target file:

```text
backend/app/config/models.py
```

Task:

Create Pydantic models for app configuration.

Support:

- Apps
- Resources
- Fields
- Field types
- Required flags
- File settings
- Basic auth defaults

Required field types:

```text
string
text
integer
number
boolean
datetime
json
list
```

Acceptance Criteria:

- Pydantic models validate a sample config.
- Invalid field types produce clear validation errors.
- Models are typed and documented with comments.

---

### TODO 009: Create Config Loader

Agent:

```text
MiniMax 2.7
```

Target files:

```text
backend/app/config/loader.py
backend/app/config/__init__.py
```

Task:

Create a config loader that reads `config/apps.yaml`.

Requirements:

- Path configurable via environment variable.
- Load YAML.
- Validate using config models.
- Cache loaded config.
- Provide helper methods:
  - `get_app(app_id)`
  - `get_resource(app_id, resource_name)`
  - `list_apps()`

Acceptance Criteria:

- Valid config loads successfully.
- Missing config file produces a clear error.
- Invalid config produces startup-readable error.

---

### TODO 010: Add App Registry API

Agent:

```text
MiniMax 2.7
```

Target files:

```text
backend/app/config/routes.py
backend/app/main.py
```

Task:

Expose app registry endpoints.

Endpoints:

```http
GET /api/apps
GET /api/apps/{app_id}
```

Acceptance Criteria:

- Returns app list from YAML config.
- Returns single app definition by ID.
- Unknown app returns 404.

---

## 5.3 SQLite Data Layer Tasks

### TODO 011: Create Database Session Module

Agent:

```text
MiniMax 2.7
```

Target file:

```text
backend/app/db/session.py
```

Task:

Create SQLite engine/session handling.

Requirements:

- Use configured `SQLITE_PATH`.
- Enable SQLite pragmas:
  - WAL mode
  - foreign keys
  - busy timeout
  - synchronous normal
- Provide session dependency for FastAPI.

Acceptance Criteria:

- Session can be imported.
- DB file is created at configured path.
- Pragmas are applied.

---

### TODO 012: Create Database Models

Agent:

```text
MiniMax 2.7
```

Target file:

```text
backend/app/db/models.py
```

Task:

Create SQLAlchemy or SQLModel models.

Tables:

- `apps`
- `records`
- `files`
- `api_tokens`
- `events`
- `jobs`
- `backup_runs`

Acceptance Criteria:

- Models match PRD schema.
- Tables can be created from models.
- JSON fields are stored as text or JSON-compatible columns.

---

### TODO 013: Create DB Initialization Script

Agent:

```text
MiniMax 2.7
```

Target files:

```text
backend/app/db/init_db.py
scripts/init_db.sh
```

Task:

Create a script that initializes the SQLite database.

Requirements:

- Create all tables.
- Apply SQLite pragmas.
- Safe to run multiple times.
- Does not delete existing data.

Acceptance Criteria:

- Running script creates DB.
- Re-running script does not fail.
- Tables exist afterward.

---

### TODO 014: Add DB Status to Health Endpoint

Agent:

```text
MiniMax 2.7
```

Target file:

```text
backend/app/health/routes.py
```

Task:

Update health endpoint to check SQLite connectivity.

Acceptance Criteria:

- Health returns `"db": "ok"` when DB is reachable.
- Health returns `"db": "error"` with safe error info when not reachable.
- No secrets are exposed.

---

## 5.4 Generic Records API Tasks

### TODO 015: Create Record Schemas

Agent:

```text
MiniMax 2.7
```

Target file:

```text
backend/app/records/schemas.py
```

Task:

Create Pydantic schemas for generic records.

Required schemas:

- `RecordCreate`
- `RecordUpdate`
- `RecordOut`
- `RecordListOut`

Acceptance Criteria:

- Schemas support JSON `data`.
- Schemas include timestamps.
- Schemas include `app_id`, `resource`, and `id`.

---

### TODO 016: Create Record Service

Agent:

```text
MiniMax 2.7
```

Target file:

```text
backend/app/records/service.py
```

Task:

Create service functions for generic records.

Functions:

- `list_records(app_id, resource)`
- `create_record(app_id, resource, data)`
- `get_record(record_id)`
- `update_record(record_id, data)`
- `soft_delete_record(record_id)`

Requirements:

- Validate app/resource exists in config.
- Validate required fields.
- Store `data_json`.
- Use soft delete.

Acceptance Criteria:

- Records can be created and read.
- Deleted records are excluded from list by default.
- Unknown app/resource returns useful error.

---

### TODO 017: Create Record Routes

Agent:

```text
MiniMax 2.7
```

Target files:

```text
backend/app/records/routes.py
backend/app/main.py
```

Task:

Create REST routes for generic resources.

Endpoints:

```http
GET    /api/{app_id}/{resource}
POST   /api/{app_id}/{resource}
GET    /api/{app_id}/{resource}/{record_id}
PATCH  /api/{app_id}/{resource}/{record_id}
DELETE /api/{app_id}/{resource}/{record_id}
```

Acceptance Criteria:

- CRUD works for sample `junk-drawer` resources.
- Unknown record returns 404.
- Deleted records do not appear in list.

---

### TODO 018: Add Record Tests

Agent:

```text
MiniMax 2.7
```

Target file:

```text
backend/tests/test_records.py
```

Task:

Add tests for record CRUD.

Acceptance Criteria:

- Test create record.
- Test list records.
- Test update record.
- Test soft delete.
- Test unknown resource.
- Tests pass with temporary SQLite database.

---

## 5.5 Authentication Tasks

### TODO 019: Create Password Hash Utility

Agent:

```text
MiniMax 2.7
```

Target files:

```text
backend/app/auth/password.py
scripts/create_admin_hash.py
```

Task:

Create password hashing and verification utilities.

Requirements:

- Use Argon2id or bcrypt.
- Script accepts password interactively.
- Script outputs hash suitable for `.env`.
- Never print the raw password.
- Never write the password or hash into tracked files automatically.

Acceptance Criteria:

- Password can be hashed.
- Hash can be verified.
- Raw password is never logged.

---

### TODO 020: Create Bearer Token Utility

Agent:

```text
MiniMax 2.7
```

Target files:

```text
backend/app/auth/tokens.py
scripts/create_token.py
```

Task:

Create bearer token generation and hashing utilities.

Requirements:

- Generate secure random tokens.
- Store only token hash.
- Support token prefix for identification if desired.
- Support scope JSON.
- Raw token is shown only once.
- Never write generated token into tracked files.

Acceptance Criteria:

- Token can be generated.
- Token hash can be verified.
- Raw token is shown only once.

---

### TODO 021: Create Auth Dependencies

Agent:

```text
MiniMax 2.7
```

Target file:

```text
backend/app/auth/dependencies.py
```

Task:

Create FastAPI dependencies for auth.

Requirements:

- Optional bearer token dependency.
- Required bearer token dependency.
- Scope checking helper.
- Admin session helper placeholder.

Acceptance Criteria:

- Protected endpoint can require token.
- Invalid token returns 401.
- Missing token returns 401 where required.
- Scope failure returns 403.

---

### TODO 022: Add Token Storage and Admin Token Creation

Agent:

```text
MiniMax 2.7
```

Target files:

```text
backend/app/auth/routes.py
backend/app/auth/tokens.py
```

Task:

Create admin-only API endpoints for token management.

Endpoints:

```http
POST /admin/tokens
GET  /admin/tokens
POST /admin/tokens/{id}/revoke
```

Acceptance Criteria:

- Admin can create token.
- Token is shown only once.
- Token list does not expose raw token.
- Token can be revoked.

---

### TODO 023: Protect Record Routes with Bearer Auth

Agent:

```text
MiniMax 2.7
```

Target file:

```text
backend/app/records/routes.py
```

Task:

Require bearer token access for record write operations.

Rules:

- Reads may be public or token-protected based on config.
- Writes require token by default.
- Token scopes should be checked by app ID.

Acceptance Criteria:

- Unauthorized writes fail.
- Authorized writes succeed.
- Scope mismatch fails.

---

## 5.6 MinIO File Storage Tasks

### TODO 024: Create MinIO Init Script

Agent:

```text
Codex / Opencode
```

Target files:

```text
scripts/init_minio.sh
docker-compose.dev.yml
docker-compose.yml
```

Task:

Create script/container setup to initialize the MinIO bucket.

Requirements:

- Create bucket if missing.
- Do not fail if bucket exists.
- Use env values.
- Do not expose MinIO publicly in production.

Acceptance Criteria:

- MinIO bucket exists after Compose startup.
- Script is idempotent.
- No MinIO secret values are committed.

---

### TODO 025: Create Storage Client

Agent:

```text
MiniMax 2.7
```

Target file:

```text
backend/app/files/storage.py
```

Task:

Create a storage client wrapper for MinIO/S3-compatible storage.

Functions:

- `put_file`
- `get_file`
- `delete_file`
- `file_exists`
- `generate_object_key`

Acceptance Criteria:

- Uses env-configured endpoint and credentials.
- Can upload a file stream.
- Can download a file stream.
- Does not expose MinIO directly to public.

---

### TODO 026: Create File Schemas and Service

Agent:

```text
MiniMax 2.7
```

Target files:

```text
backend/app/files/schemas.py
backend/app/files/service.py
```

Task:

Create file metadata schemas and service logic.

Requirements:

- Store file metadata in `files` table.
- Validate app/resource exists.
- Validate allowed file types if configured.
- Generate safe object keys.

Acceptance Criteria:

- Upload creates metadata row.
- File metadata includes size/content type.
- Invalid file type is rejected if config specifies allowed types.

---

### TODO 027: Create File Routes

Agent:

```text
MiniMax 2.7
```

Target files:

```text
backend/app/files/routes.py
backend/app/main.py
```

Task:

Create API routes for file upload/download/list/delete.

Endpoints:

```http
POST   /api/{app_id}/{resource}/{record_id}/files
GET    /api/{app_id}/{resource}/{record_id}/files
GET    /api/files/{file_id}
DELETE /api/files/{file_id}
```

Acceptance Criteria:

- Upload works.
- List files for record works.
- Download streams file.
- Delete soft-deletes metadata and removes object or marks deleted.
- Unauthorized upload fails.

---

### TODO 028: Add Storage Status to Health Endpoint

Agent:

```text
MiniMax 2.7
```

Target file:

```text
backend/app/health/routes.py
```

Task:

Update health endpoint to check storage connectivity.

Acceptance Criteria:

- Health returns `"storage": "ok"` when MinIO is reachable.
- Health returns `"storage": "error"` when unreachable.
- No secrets are exposed.

---

## 5.7 Admin UI Tasks

### TODO 029: Create Admin Base Template and CSS

Agent:

```text
MiniMax 2.7
```

Target files:

```text
backend/app/admin/templates/base.html
backend/app/static/admin.css
```

Task:

Create a simple admin layout.

Requirements:

- Clean, readable layout.
- Navigation for dashboard, apps, records, files, tokens, backups.
- Mobile-tolerant but not fancy.
- No build step.

Acceptance Criteria:

- Base template renders.
- CSS loads.
- Navigation links exist.

---

### TODO 030: Create Admin Login Page

Agent:

```text
MiniMax 2.7
```

Target files:

```text
backend/app/admin/templates/login.html
backend/app/admin/routes.py
```

Task:

Create admin login page and login route.

Requirements:

- Verify password against `ADMIN_PASSWORD_HASH`.
- Set secure HTTP-only session cookie.
- Show safe error on failed login.

Acceptance Criteria:

- Correct password logs in.
- Wrong password fails.
- Session cookie is HTTP-only.
- Admin pages require session.

---

### TODO 031: Create Admin Dashboard

Agent:

```text
MiniMax 2.7
```

Target files:

```text
backend/app/admin/templates/dashboard.html
backend/app/admin/routes.py
```

Task:

Create admin dashboard.

Display:

- App version
- Host
- DB status
- Storage status
- Number of apps
- Number of records
- Number of files
- Last backup status

Acceptance Criteria:

- Dashboard renders after login.
- Counts are accurate.
- Backup status placeholder works even before backup implementation.

---

### TODO 032: Create Admin App and Record Browser

Agent:

```text
MiniMax 2.7
```

Target files:

```text
backend/app/admin/templates/apps.html
backend/app/admin/templates/records.html
backend/app/admin/routes.py
```

Task:

Create simple admin screens for apps and records.

Requirements:

- List configured apps.
- List resources per app.
- Browse records per resource.
- View raw JSON record data.

Acceptance Criteria:

- Admin can inspect records.
- Deleted records are visually identified or hidden by default.
- No editing required in this task.

---

### TODO 033: Create Admin File Browser

Agent:

```text
MiniMax 2.7
```

Target files:

```text
backend/app/admin/templates/files.html
backend/app/admin/routes.py
```

Task:

Create simple file browser.

Requirements:

- List file metadata.
- Link to download route.
- Show app/resource/record association.
- Show size and content type.

Acceptance Criteria:

- Admin can view uploaded files.
- Admin can download file via API route.

---

### TODO 034: Create Admin Token Manager UI

Agent:

```text
MiniMax 2.7
```

Target files:

```text
backend/app/admin/templates/tokens.html
backend/app/admin/routes.py
```

Task:

Create token management screen.

Requirements:

- List tokens without raw values.
- Create token with name and scopes JSON.
- Show newly created token once.
- Revoke token.

Acceptance Criteria:

- Admin can create token.
- Admin can copy token once.
- Revoked token no longer works.

---

## 5.8 Backup Tasks

### TODO 035: Create Restic Backup Script

Agent:

```text
Codex / Opencode
```

Target file:

```text
scripts/backup_now.sh
```

Task:

Create shell script for running a backup.

Requirements:

- Read environment variables.
- Create SQLite backup copy with `.backup`.
- Run Restic backup to Cloudflare R2.
- Include config, SQLite backup, MinIO data, deployment files.
- Run retention policy.
- Exit nonzero on failure.
- Never print secrets.
- Never commit R2 credentials.

Acceptance Criteria:

- Script runs manually on VPS.
- Restic snapshot appears in R2.
- Backup is encrypted.
- Script logs useful output without secrets.

---

### TODO 036: Create Restore Script

Agent:

```text
Codex / Opencode
```

Target files:

```text
scripts/restore_latest.sh
docs/backup-restore.md
```

Task:

Create restore helper and documentation.

Requirements:

- Restore latest Restic snapshot to specified directory.
- Document how to restore SQLite.
- Document how to restore MinIO data.
- Document how to test restore locally.
- Never overwrite live data by default.

Acceptance Criteria:

- Restore script can restore to temp directory.
- Docs are clear enough to follow later.
- Does not overwrite live data by default.

---

### TODO 037: Create Backup Service

Agent:

```text
MiniMax 2.7
```

Target file:

```text
backend/app/backups/service.py
```

Task:

Create Python service for recording backup run metadata.

Functions:

- `start_backup_run(destination)`
- `finish_backup_run_success(run_id, snapshot_id, bytes_added)`
- `finish_backup_run_failure(run_id, error)`
- `get_latest_backup_run()`
- `list_backup_runs()`

Acceptance Criteria:

- Backup runs can be recorded.
- Latest backup can be retrieved.
- Errors are stored safely.

---

### TODO 038: Create Backup Routes

Agent:

```text
MiniMax 2.7
```

Target files:

```text
backend/app/backups/routes.py
backend/app/main.py
```

Task:

Create admin backup routes.

Endpoints:

```http
GET  /admin/backups
POST /admin/backups/run
```

Requirements:

- `GET` shows backup history.
- `POST` triggers backup script or queues backup job.
- Must require admin session.

Acceptance Criteria:

- Admin can view backup history.
- Admin can trigger manual backup.
- Backup result is recorded.

---

### TODO 039: Create Backup Admin Page

Agent:

```text
MiniMax 2.7
```

Target file:

```text
backend/app/admin/templates/backups.html
```

Task:

Create backup status page.

Display:

- Last backup time
- Last backup status
- Snapshot ID if available
- Error if failed
- Manual backup button
- Warning if no successful backup in 48 hours

Acceptance Criteria:

- Page renders.
- Manual backup button works.
- Failure state is visible.

---

### TODO 040: Add Backup Schedule to Worker

Agent:

```text
Codex / Opencode
```

Target files:

```text
backend/app/jobs/worker.py
docker-compose.yml
```

Task:

Create background worker that runs scheduled backup.

Requirements:

- Run nightly at 3:30 AM server time.
- Use configured timezone.
- Record backup result.
- Avoid overlapping backups.

Acceptance Criteria:

- Worker starts in Docker.
- Scheduled job is registered.
- Manual test run works.
- Logs show backup start/end.

---

## 5.9 Production Deployment Tasks

### TODO 041: Create Production Docker Compose

Agent:

```text
Codex / Opencode
```

Target file:

```text
docker-compose.yml
```

Task:

Create production Docker Compose file.

Services:

- `caddy`
- `api`
- `worker`
- `minio`
- `backup` if needed

Requirements:

- Persistent volumes under `/opt/labbox`.
- MinIO not publicly exposed.
- API exposed only through Caddy.
- Environment loaded from `.env`.
- `.env` must be present on VPS but never committed.

Acceptance Criteria:

- Compose starts on VPS.
- Services restart unless stopped.
- No public MinIO ports exposed.
- Secrets are loaded from `.env`.

---

### TODO 042: Create Caddyfile

Agent:

```text
Codex / Opencode
```

Target file:

```text
Caddyfile
```

Task:

Create Caddy reverse proxy config.

Domain:

```text
labs.smallbizguru.com
```

Routes:

- `/api/*` -> API
- `/admin*` -> API/admin
- `/files/*` -> API
- `/` -> API/admin or landing page

Acceptance Criteria:

- HTTPS works.
- API health endpoint works publicly.
- Admin UI works publicly.
- MinIO remains private.

---

### TODO 043: Create VPS Setup Script

Agent:

```text
Codex / Opencode
```

Target file:

```text
scripts/vps_setup.sh
```

Task:

Create setup script for fresh Hetzner VPS.

Requirements:

- Update packages.
- Install Docker.
- Install Docker Compose plugin.
- Install useful tools:
  - git
  - sqlite3
  - ufw
  - curl
  - restic
- Configure firewall:
  - allow 22
  - allow 80
  - allow 443
- Create `/opt/labbox`.
- Do not create `.env` with fake secrets except as an example copy step.

Acceptance Criteria:

- Script can be run on fresh VPS.
- Docker works afterward.
- Firewall is configured.
- `/opt/labbox` exists.

---

### TODO 044: Create Deployment Documentation

Agent:

```text
Codex / Opencode
```

Target file:

```text
docs/deployment.md
```

Task:

Document deployment to `labs.smallbizguru.com`.

Include:

- Existing GitHub repo assumption
- DNS assumption
- VPS setup
- Clone repo or pull latest
- Confirm `.gitignore` protects `.env`
- Copy `.env.example` to `.env`
- Generate admin password hash
- Generate session/token secrets
- Generate MinIO credentials
- Create Cloudflare R2 bucket
- Create Cloudflare R2 access keys
- Fill in `.env`
- Start Docker Compose
- Check health endpoint
- Create first token
- Run first backup
- Confirm `.env` is not staged or committed

Acceptance Criteria:

- Docs can be followed from a fresh VPS.
- No missing critical secret steps.
- No real secrets included.
- Explicitly warns never to commit `.env`.

---

### TODO 045: First Production Deployment

Agent:

```text
Codex / Opencode
```

Task:

Deploy MVP to VPS.

Requirements:

- App available at `https://labs.smallbizguru.com`.
- Health endpoint available.
- Admin login available.
- SQLite initialized.
- MinIO initialized.
- R2 backup configured.
- First manual backup succeeds.
- `.env` exists on VPS.
- `.env` is not in Git.

Acceptance Criteria:

```http
GET https://labs.smallbizguru.com/api/health
```

returns healthy response.

Admin UI works.

First backup snapshot exists in Cloudflare R2.

`git status --short` does not show `.env` staged or tracked.

---

## 5.10 Documentation Tasks

### TODO 046: Create README

Agent:

```text
MiniMax 2.7
```

Target file:

```text
README.md
```

Task:

Create project README.

Include:

- What LabBox is
- What it is not
- Existing repo assumption
- Local development
- Production deployment pointer
- Basic API examples
- Backup warning
- Config-driven app concept
- Secret warning: never commit `.env`

Acceptance Criteria:

- README is useful to future self.
- README does not overstate production readiness.
- README clearly states `.env` must never be committed.

---

### TODO 047: Create App Config Documentation

Agent:

```text
MiniMax 2.7
```

Target file:

```text
docs/app-config.md
```

Task:

Document how to add a new app/resource.

Include:

- Example app
- Field types
- Required fields
- File config
- Auth defaults
- How to reload/restart after config change

Acceptance Criteria:

- A new app can be added by following docs.
- Example config validates.

---

### TODO 048: Create API Usage Examples

Agent:

```text
MiniMax 2.7
```

Target file:

```text
docs/api-examples.md
```

Task:

Create API examples using curl.

Include:

- List apps
- Create record
- List records
- Update record
- Delete record
- Upload file
- Download file

Acceptance Criteria:

- Examples use `labs.smallbizguru.com`.
- Examples include bearer token placeholder.
- Examples are copy/paste friendly.
- No real bearer token is included.

---

# 6. MiniMax Task Prompt Template

Use this template when handing coding tasks to MiniMax 2.7.

```markdown
You are working on LabBox Backend, a small Dockerized FastAPI backend for personal experiments.

Important repo context:
- The project directory already exists.
- Git has already been initialized.
- A remote GitHub repo is already associated.
- Work in the current directory.
- Do not create a new high-level wrapper directory.
- Do not run git init.
- Do not add or change Git remotes.

Project stack:
- Python 3.12+
- FastAPI
- SQLite
- SQLAlchemy or SQLModel
- Pydantic
- MinIO/S3-compatible storage
- Docker Compose

Critical secret rules:
- Never commit real secrets.
- Never write real secrets into tracked files.
- The real .env file must never be added to git.
- .env.example may contain placeholders only.
- If touching .gitignore, ensure it includes:
  .env
  .env.*
  !.env.example

Important constraints:
- Keep the task narrow.
- Modify only the files listed unless absolutely necessary.
- Use type hints.
- Do not redesign the whole architecture.
- Prefer boring, readable code.
- Include tests if the task asks for them.
- Return the full contents of changed files.

Task:
[PASTE TODO TASK HERE]

Acceptance criteria:
[PASTE ACCEPTANCE CRITERIA HERE]
```

---

# 7. Codex / Opencode Task Prompt Template

Use this template when handing setup/integration/deployment tasks to Codex or Opencode.

```markdown
You are working on LabBox Backend, a Dockerized personal experiment backend deployed to:

https://labs.smallbizguru.com

Important repo context:
- The project directory already exists.
- Git has already been initialized.
- A remote GitHub repo is already associated.
- Work in the current directory.
- Do not create a new high-level wrapper directory.
- Do not run git init.
- Do not add or change Git remotes unless explicitly asked.

Your role:
- Setup
- Integration
- Deployment
- Docker
- Caddy
- VPS orchestration
- Review and assembly of MiniMax-produced code

Stack:
- Python 3.12+
- FastAPI
- SQLite
- MinIO
- Caddy
- Restic
- Cloudflare R2
- Docker Compose
- Hetzner VPS

Critical secret rules:
- Never commit real secrets.
- Never write real secrets into tracked files.
- The real .env file must never be added to git.
- .env.example may contain placeholders only.
- Ensure .gitignore includes:
  .env
  .env.*
  !.env.example
- Deployment docs must include a secrets setup step.
- Before commit or deploy, check:
  git status --short
- Confirm .env is not staged or tracked.

Important constraints:
- Use Docker Compose, not Kubernetes.
- Keep MinIO private by default.
- Use Caddy for HTTPS.
- Prefer simple, inspectable deployment.
- Preserve existing code unless a change is necessary.
- Run or describe validation steps.

Task:
[PASTE TODO TASK HERE]

Acceptance criteria:
[PASTE ACCEPTANCE CRITERIA HERE]
```

---

# 8. Suggested Execution Order Summary

Use this short checklist as the main implementation order.

```text
[ ] 001 Audit existing repository
[ ] 002 Create or update .gitignore
[ ] 003 Create base project files
[ ] 004 Create Python project configuration
[ ] 005 Create FastAPI app skeleton
[ ] 006 Create backend Dockerfile
[ ] 007 Create Docker Compose development stack

[ ] 008 Define app config schema
[ ] 009 Create config loader
[ ] 010 Add app registry API

[ ] 011 Create database session module
[ ] 012 Create database models
[ ] 013 Create DB initialization script
[ ] 014 Add DB status to health endpoint

[ ] 015 Create record schemas
[ ] 016 Create record service
[ ] 017 Create record routes
[ ] 018 Add record tests

[ ] 019 Create password hash utility
[ ] 020 Create bearer token utility
[ ] 021 Create auth dependencies
[ ] 022 Add token storage and admin token creation
[ ] 023 Protect record routes with bearer auth

[ ] 024 Create MinIO init script
[ ] 025 Create storage client
[ ] 026 Create file schemas and service
[ ] 027 Create file routes
[ ] 028 Add storage status to health endpoint

[ ] 029 Create admin base template and CSS
[ ] 030 Create admin login page
[ ] 031 Create admin dashboard
[ ] 032 Create admin app and record browser
[ ] 033 Create admin file browser
[ ] 034 Create admin token manager UI

[ ] 035 Create Restic backup script
[ ] 036 Create restore script
[ ] 037 Create backup service
[ ] 038 Create backup routes
[ ] 039 Create backup admin page
[ ] 040 Add backup schedule to worker

[ ] 041 Create production Docker Compose
[ ] 042 Create Caddyfile
[ ] 043 Create VPS setup script
[ ] 044 Create deployment documentation
[ ] 045 First production deployment

[ ] 046 Create README
[ ] 047 Create app config documentation
[ ] 048 Create API usage examples
```

---

# 9. Definition of Done

LabBox Backend implementation is considered done when:

- The app is deployed at `https://labs.smallbizguru.com`.
- Health endpoint returns healthy DB and storage status.
- Admin can log in.
- Admin can create bearer tokens.
- A sample app is defined in YAML.
- Records can be created, listed, updated, and soft-deleted.
- Files can be uploaded to MinIO and downloaded through the API.
- MinIO is not publicly exposed.
- Cloudflare R2 backups work.
- Manual backup works.
- Nightly backup is scheduled.
- Backup history is visible in admin.
- Restore process is documented.
- README and app config docs are complete.
- `.env` is not tracked by Git.
- `.env.example` contains placeholders only.
- Deployment docs explain all secret setup steps.
- The system remains small, understandable, and appropriate for personal experiments.

---

# 10. Guiding Principle

LabBox Backend should help future experiments move faster without becoming a platform monster.

The working standard:

> Add config when the need is common.  
> Add code when the experiment gets weird.  
> Keep the whole thing boring enough that future-you can fix it at midnight.
