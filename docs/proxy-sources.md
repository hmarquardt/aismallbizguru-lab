# Proxy Sources

Proxy Sources let LabBox call named upstream APIs on behalf of static frontend pages.

They are intentionally not an open CORS proxy. Browser callers use:

```http
GET /api/proxy/{slug}?param=value
```

The `{slug}` must match an enabled source saved by an admin in SQLite. Public callers cannot provide an arbitrary upstream URL.

## Create a Source

Open the LabBox admin UI and go to **Proxy Sources**.

Create or edit a source with:

- Name
- Slug
- Description
- Enabled
- Public
- Config JSON

Use **Test Source** with sample query params before calling the source from a static page.

## Config

Example Open-Meteo config:

```json
{
  "base_url": "https://api.open-meteo.com/v1/forecast",
  "method": "GET",
  "allowed_query_params": [
    "latitude",
    "longitude",
    "current",
    "hourly",
    "daily",
    "timezone",
    "temperature_unit",
    "wind_speed_unit",
    "precipitation_unit"
  ],
  "required_query_params": ["latitude", "longitude"],
  "allowed_response_content_types": ["application/json"],
  "cache_ttl_seconds": 300,
  "timeout_seconds": 10,
  "max_response_bytes": 1048576,
  "follow_redirects": false,
  "auth": {
    "mode": "public",
    "scope_app": null,
    "required_scope": "read"
  }
}
```

`cache_ttl_seconds` is reserved for a later persistent cache pass. Current V1 requests are fetched live and reported as `cache_status: "bypass"` in admin tests.

## Static Frontend Usage

```js
const API_BASE = "https://lab.aismallbizguru.com/api";

async function proxyFetch(sourceSlug, params = {}) {
  const url = new URL(`${API_BASE}/proxy/${sourceSlug}`);
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, value);
    }
  }

  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Proxy request failed: ${response.status}`);
  }

  return response.json();
}

const weather = await proxyFetch("open-meteo", {
  latitude: 38.3553,
  longitude: -87.5675,
  current: "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
  timezone: "America/Indiana/Indianapolis"
});
```

## Access Control

Set `public: true` or `auth.mode: "public"` for sources that can be called without a bearer token.

Private sources require an existing LabBox bearer token. If `auth.scope_app` is set, LabBox checks the token for `auth.required_scope` on that app. If `auth.scope_app` is not set, any valid non-revoked bearer token is accepted.

## Security Notes

Proxy Sources only support `GET` in V1.

LabBox rejects:

- Unknown or disabled source slugs
- Query params not listed in `allowed_query_params`
- Requests missing `required_query_params`
- Unsupported upstream schemes such as `file`, `ftp`, `gopher`, `data`, and `javascript`
- Localhost, loopback, private, link-local, and unique-local upstream targets
- Responses with content types outside `allowed_response_content_types`
- Responses larger than `max_response_bytes`

LabBox does not forward browser `Authorization`, cookies, or arbitrary request headers upstream.

## Limitations

- V1 supports GET only.
- Request header forwarding is not enabled.
- Persistent caching is not implemented yet.
- Admin config editing is a JSON textarea, not a schema-driven editor.
