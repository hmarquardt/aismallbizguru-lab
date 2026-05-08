#!/usr/bin/env bash
set -Eeuo pipefail

log() {
  printf '[backup] %s\n' "$*"
}

fail() {
  printf '[backup] ERROR: %s\n' "$*" >&2
  exit 1
}

load_env_file() {
  local env_file="${ENV_FILE:-/opt/labbox/.env}"
  if [[ -f "$env_file" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$env_file"
    set +a
  fi
}

require_env() {
  local name="$1"
  [[ -n "${!name:-}" ]] || fail "missing required environment variable: ${name}"
}

load_env_file

SQLITE_PATH="${SQLITE_PATH:-/data/sqlite/labbox.db}"
BACKUP_STAGING_DIR="${BACKUP_STAGING_DIR:-/backup-staging}"
MINIO_DATA_DIR="${MINIO_DATA_DIR:-/data/minio}"
CONFIG_DIR="${CONFIG_DIR:-/config}"
DEPLOY_DIR="${DEPLOY_DIR:-/opt/labbox}"
BACKUP_INCLUDE_ENV="${BACKUP_INCLUDE_ENV:-false}"

require_env RESTIC_REPOSITORY
require_env RESTIC_PASSWORD
require_env R2_ACCESS_KEY_ID
require_env R2_SECRET_ACCESS_KEY

export AWS_ACCESS_KEY_ID="$R2_ACCESS_KEY_ID"
export AWS_SECRET_ACCESS_KEY="$R2_SECRET_ACCESS_KEY"
export AWS_DEFAULT_REGION="${S3_REGION:-us-east-1}"

command -v sqlite3 >/dev/null 2>&1 || fail "sqlite3 is not installed"
command -v restic >/dev/null 2>&1 || fail "restic is not installed"

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
snapshot_dir="${BACKUP_STAGING_DIR}/${timestamp}"
sqlite_backup="${snapshot_dir}/sqlite/labbox.db"

mkdir -p "${snapshot_dir}/sqlite"

if [[ -f "$SQLITE_PATH" ]]; then
  log "creating SQLite backup copy"
  sqlite3 "$SQLITE_PATH" ".backup '${sqlite_backup}'"
else
  log "SQLite file does not exist yet; writing placeholder"
  printf 'SQLite database was not present at backup time: %s\n' "$SQLITE_PATH" > "${snapshot_dir}/sqlite/README.txt"
fi

restic snapshots >/dev/null 2>&1 || {
  log "initializing restic repository"
  restic init
}

backup_paths=("$snapshot_dir")

if [[ -d "$CONFIG_DIR" ]]; then
  backup_paths+=("$CONFIG_DIR")
fi

if [[ -d "$MINIO_DATA_DIR" ]]; then
  backup_paths+=("$MINIO_DATA_DIR")
fi

if [[ -f "${DEPLOY_DIR}/docker-compose.yml" ]]; then
  backup_paths+=("${DEPLOY_DIR}/docker-compose.yml")
fi

if [[ -f "${DEPLOY_DIR}/Caddyfile" ]]; then
  backup_paths+=("${DEPLOY_DIR}/Caddyfile")
fi

if [[ "$BACKUP_INCLUDE_ENV" == "true" && -f "${DEPLOY_DIR}/.env" ]]; then
  backup_paths+=("${DEPLOY_DIR}/.env")
fi

log "running encrypted restic backup"
restic backup "${backup_paths[@]}" --tag labbox

log "applying retention policy"
restic forget \
  --keep-daily "${BACKUP_RETENTION_DAILY:-7}" \
  --keep-weekly "${BACKUP_RETENTION_WEEKLY:-4}" \
  --keep-monthly "${BACKUP_RETENTION_MONTHLY:-6}" \
  --prune

log "backup complete"
