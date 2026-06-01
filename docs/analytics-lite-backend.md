# Analytics Lite Backend

JunkStats / Analytics Lite is a small Google Analytics-style backend for static GitHub Pages apps. It runs inside the LabBox FastAPI service, but it does not use the generic LabBox records/resources tables. Analytics data lives in its own SQLite file, schema, router, ingestion path, and query layer.

## Environment Variables

```text
ANALYTICS_DB_PATH=/data/analytics/analytics.sqlite
ANALYTICS_DASHBOARD_TOKEN=change-me
ANALYTICS_IP_HASH_PEPPER=change-me
ANALYTICS_ALLOWED_ORIGINS=https://hmarquardt.github.io,https://lab.aismallbizguru.com
```

`ANALYTICS_DB_PATH` controls the dedicated SQLite database. `ANALYTICS_DASHBOARD_TOKEN` protects reporting endpoints. `ANALYTICS_IP_HASH_PEPPER` is used to hash IP addresses before storage. `ANALYTICS_ALLOWED_ORIGINS` is a comma-separated browser origin allowlist for collection requests.

## API Endpoints

- `GET /api/analytics/health`
- `POST /api/analytics/collect`
- `GET /api/analytics/summary?site_id=junkdrawer&from=YYYY-MM-DD&to=YYYY-MM-DD`
- `GET /api/analytics/timeseries?site_id=junkdrawer&from=YYYY-MM-DD&to=YYYY-MM-DD&bucket=day`
- `GET /api/analytics/pages?site_id=junkdrawer&from=YYYY-MM-DD&to=YYYY-MM-DD`
- `GET /api/analytics/referrers?site_id=junkdrawer&from=YYYY-MM-DD&to=YYYY-MM-DD`
- `GET /api/analytics/recent?site_id=junkdrawer`

Dashboard endpoints require:

```text
Authorization: Bearer <ANALYTICS_DASHBOARD_TOKEN>
```

## Example Collect Request

```bash
curl -X POST https://lab.aismallbizguru.com/api/analytics/collect \
  -H 'Content-Type: application/json' \
  -H 'Origin: https://hmarquardt.github.io' \
  -d '{
    "site_id": "junkdrawer",
    "event_type": "pageview",
    "visitor_id": "v_example",
    "session_id": "s_example",
    "occurred_at": "2026-05-30T12:34:56.000Z",
    "page": {
      "url": "https://hmarquardt.github.io/junkdrawer/weather_nerd.html",
      "title": "Weather Nerd"
    },
    "client": {
      "language": "en-US",
      "timezone": "America/Indiana/Indianapolis",
      "user_agent": "Mozilla/5.0 ..."
    }
  }'
```

## Example Dashboard Query

```bash
curl 'https://lab.aismallbizguru.com/api/analytics/summary?site_id=junkdrawer&from=2026-05-01&to=2026-05-30' \
  -H 'Authorization: Bearer change-me'
```

## Privacy Notes

Raw IP addresses are never stored. The backend stores a SHA-256 hash of the IP address plus `ANALYTICS_IP_HASH_PEPPER`. User agents are hashed and also parsed into coarse browser, operating system, and device fields. Obvious bots are flagged so dashboard queries can ignore them by default.

## Deployment Notes

The production Docker Compose file already mounts `./data:/data`, which persists `/data/analytics/analytics.sqlite`. The development compose file mounts `./data/analytics:/data/analytics`.

The analytics schema is created automatically on startup or first database access. The default `junkdrawer` site is seeded if missing with origin `https://hmarquardt.github.io`.

## Verifying Writes

1. Check health:

   ```bash
   curl https://lab.aismallbizguru.com/api/analytics/health
   ```

2. Send a collect request.

3. Confirm SQLite tables have rows:

   ```bash
   sqlite3 data/analytics/analytics.sqlite \
     'SELECT COUNT(*) FROM pageviews; SELECT COUNT(*) FROM visitors; SELECT COUNT(*) FROM sessions;'
   ```

