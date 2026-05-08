#!/usr/bin/env bash
set -Eeuo pipefail

fail() {
  printf '[restore] ERROR: %s\n' "$*" >&2
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

target="${1:-}"
[[ -n "$target" ]] || fail "usage: scripts/restore_latest.sh /path/to/empty/restore-dir"

mkdir -p "$target"

if find "$target" -mindepth 1 -maxdepth 1 | read -r _; then
  fail "restore target is not empty: $target"
fi

load_env_file

[[ -n "${RESTIC_REPOSITORY:-}" ]] || fail "missing RESTIC_REPOSITORY"
[[ -n "${RESTIC_PASSWORD:-}" ]] || fail "missing RESTIC_PASSWORD"
[[ -n "${R2_ACCESS_KEY_ID:-}" ]] || fail "missing R2_ACCESS_KEY_ID"
[[ -n "${R2_SECRET_ACCESS_KEY:-}" ]] || fail "missing R2_SECRET_ACCESS_KEY"

export AWS_ACCESS_KEY_ID="$R2_ACCESS_KEY_ID"
export AWS_SECRET_ACCESS_KEY="$R2_SECRET_ACCESS_KEY"
export AWS_DEFAULT_REGION="${S3_REGION:-us-east-1}"

restic restore latest --target "$target"
printf '[restore] restored latest snapshot to %s\n' "$target"
