# LabBox Backend

Lightweight backend appliance for personal experiments and small private web tools.

The initial target deployment is:

```text
https://labs.smallbizguru.com
```

## Stack

- Python 3.12
- FastAPI
- SQLite
- MinIO
- Cloudflare R2
- Restic
- Caddy
- Docker Compose

## Local Development

Create a local environment file from the template:

```bash
cp .env.example .env
```

Start the development stack:

```bash
docker compose -f docker-compose.dev.yml up --build
```

Health check:

```bash
curl http://localhost:8010/api/health
```

Local MinIO ports:

```text
S3 API: http://localhost:9010
Console: http://localhost:9011
```

## Secrets

Never commit `.env` or real credentials. Only `.env.example` is intended to be tracked.

Required deployment secrets include admin password/session values, API token pepper, MinIO/S3 credentials, Cloudflare R2 credentials, and the Restic password.
