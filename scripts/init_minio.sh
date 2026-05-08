#!/usr/bin/env bash
set -Eeuo pipefail

endpoint="${S3_ENDPOINT:-http://minio:9000}"
bucket="${MINIO_BUCKET:-labbox-assets}"

python - <<'PY'
from app.files.storage import ensure_bucket_exists

ensure_bucket_exists()
print("MinIO bucket is ready")
PY

printf 'bucket %s is ready at %s\n' "$bucket" "$endpoint"
