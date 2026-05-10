# Wildlife Field Recorder Backend

LabBox backend configuration for the **Wildlife Field Recorder** static front-end app.

## Purpose

Provide durable storage, record APIs, file upload, and admin UI for an offline-first wildlife observation recorder. The browser frontend captures voice notes, GPS location, weather snapshots, transcriptions, classifications, and photo attachments in the field, then submits enriched records to LabBox.

The backend does **not** run transcription or LLM classification. The browser handles that via configurable providers and sends the results as JSON.

## App ID and Resources

- **App ID:** `wildlife-field-recorder`
- **Resources:**
  - `observations` — finalized field observation records
  - `trips` — trip/route groupings of observations

## Auth

Both reads and writes require a valid API token.

```yaml
auth:
  default_read: token
  default_write: token
```

> **Privacy note:** Public read is **not recommended** for this app. Observations contain exact GPS coordinates and sensitive wildlife locations. Use token-protected reads and keep tokens scoped to the minimum necessary access.

## Required Token Scope

Create a LabBox API token scoped to:

```json
{
  "wildlife-field-recorder": ["read", "write"]
}
```

The browser app stores this token in `localStorage` only when the user enters it in the Setup/Admin tab. Warn users that browser-held tokens are not secret on shared machines.

## CORS

The GitHub Pages origin and current custom domains are allowed in `CORS_ALLOW_ORIGINS`:

```env
CORS_ALLOW_ORIGINS=https://hmarquardt.github.io,https://tophatferals.com,https://www.tophatferals.com
```

If the app is served from a custom domain later, append it comma-separated:

```env
CORS_ALLOW_ORIGINS=https://hmarquardt.github.io,https://wildlife.example.com
```

## API Examples

Set these variables first:

```bash
API_BASE="https://lab.aismallbizguru.com/api"
APP="wildlife-field-recorder"
TOKEN="replace-me"
```

### Health check

```bash
curl "$API_BASE/health"
```

### List configured apps

```bash
curl "$API_BASE/apps"
```

### List observations

```bash
curl "$API_BASE/$APP/observations" \
  -H "Authorization: Bearer $TOKEN"
```

### Create observation

```bash
curl -X POST "$API_BASE/$APP/observations" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "data": {
      "localId": "local-demo-1",
      "createdAt": "2026-05-10T20:15:00Z",
      "latitude": 38.3553,
      "longitude": -87.5675,
      "gpsStatus": "ok",
      "weatherStatus": "ok",
      "weatherCondition": "cloudy",
      "temperatureF": 71.0,
      "barometricPressureHpa": 1012.1,
      "transcript": "Great blue heron standing near the edge of the lake.",
      "subjectCommonName": "Great Blue Heron",
      "category": "bird",
      "tags": ["lake", "shoreline", "heron"],
      "summary": "Great blue heron observed near water.",
      "photoCount": 0
    }
  }'
```

### Upload audio file to observation

```bash
OBS_ID="replace-with-created-record-id"

curl -X POST "$API_BASE/$APP/observations/$OBS_ID/files" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@observation.webm;type=audio/webm"
```

### Upload photo file to observation

```bash
curl -X POST "$API_BASE/$APP/observations/$OBS_ID/files" \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@heron-photo.jpg;type=image/jpeg"
```

### List trips

```bash
curl "$API_BASE/$APP/trips" \
  -H "Authorization: Bearer $TOKEN"
```

### Create trip

```bash
curl -X POST "$API_BASE/$APP/trips" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "data": {
      "localTripId": "trip-demo-1",
      "title": "Evening Wildlife Drive — May 10",
      "startedAt": "2026-05-10T20:00:00Z",
      "endedAt": "2026-05-10T22:15:00Z",
      "observationLocalIds": ["local-demo-1", "local-demo-2"],
      "observationCount": 2,
      "categories": ["bird", "reptile"],
      "centerLatitude": 38.3553,
      "centerLongitude": -87.5675,
      "totalDistanceEstimateMiles": 3.4,
      "tripSummary": "Evening wildlife drive with lakeside bird activity and one reptile sighting.",
      "routeGeoJson": {
        "type": "FeatureCollection",
        "features": []
      }
    }
  }'
```

### Create trip from clustered observations

Recommended browser workflow:

1. Save individual observations first.
2. Cluster nearby observations on the page by time and geography.
3. Ask the user only for a trip name.
4. Send the selected observation record IDs or local IDs to this endpoint.

```bash
curl -X POST "$API_BASE/$APP/trips/from-observations" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Cloudy Lake Walk",
    "observation_local_ids": ["local-demo-1", "local-demo-2"]
  }'
```

The backend creates a trip record with observation IDs, local IDs, count, categories, subject summaries, center point, bounding box, a simple route GeoJSON line, dominant weather, min/max/average temperature, and average barometric pressure.

### Create trip route with GeoJSON

The `routeGeoJson` field is stored as JSON directly on the trip record:

```bash
TRIP_ID="replace-with-created-trip-id"

curl -X PATCH "$API_BASE/$APP/trips/$TRIP_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "data": {
      "routeGeoJson": {
        "type": "FeatureCollection",
        "features": [
          {
            "type": "Feature",
            "geometry": {
              "type": "LineString",
              "coordinates": [
                [-87.5675, 38.3553],
                [-87.5680, 38.3560]
              ]
            },
            "properties": {
              "name": "Evening Drive Route"
            }
          }
        ]
      }
    }
  }'
```

## File Attachments

Observation records accept multiple attached files. The backend does not require the frontend to separate audio and photos into different resources. Both attach to the same observation record:

- **Original audio note** — captured in the field via MediaRecorder
- **Photos** — added later or at capture time
- **Supporting files** — optional manual uploads

The frontend tracks file purpose locally and in record metadata (e.g., `photoCount`). The backend preserves filename, content type, and description metadata.

For a mobile-friendly photo control, the frontend can use:

```html
<input type="file" accept="image/*" capture="environment" multiple>
```

Upload each selected photo to:

```text
POST /api/wildlife-field-recorder/observations/{OBSERVATION_RECORD_ID}/files
```

Observation responses include a `files` array. If at least one attached file is an image, the API also adds `data.photo_url` as a convenience preview URL without requiring that field to be persisted in the observation JSON.

## Review Page Guidance

The review screen should be dense enough to scan many observations. A useful row/card needs:

- species/common subject, category, count, and review status
- timestamp, short transcript or summary, and user note
- latitude/longitude, accuracy, habitat, and behavior
- `weatherCondition`, `temperatureF`, `barometricPressureHpa` or `barometricPressureInHg`, humidity, and wind if present
- photo thumbnail from `data.photo_url` or the first image in `files`
- audio/file counts and any submit/sync status

Trips created through `POST /trips/from-observations` should be listed as editable summaries, not as a separate manual upload step.

## Field Quick Reference

### Observations

| Field | Type | Required |
|---|---|---|
| localId | string | yes |
| tripLocalId | string | |
| backendTripId | string | |
| createdAt | datetime | yes |
| startedAt | datetime | |
| stoppedAt | datetime | |
| durationSeconds | number | |
| latitude | number | |
| longitude | number | |
| accuracyMeters | number | |
| altitude | number | |
| heading | number | |
| speed | number | |
| gpsStatus | string | |
| weatherStatus | string | |
| weatherCondition | string | |
| temperatureF | number | |
| temperatureC | number | |
| barometricPressureHpa | number | |
| barometricPressureInHg | number | |
| humidityPercent | number | |
| windSpeedMph | number | |
| windDirection | string | |
| weatherFetchedAt | datetime | |
| weatherRaw | json | |
| transcript | text | |
| subjectCommonName | string | |
| subjectScientificName | string | |
| subjectConfidence | number | |
| category | string | |
| categoryConfidence | number | |
| behavior | text | |
| habitat | text | |
| count | integer | |
| tags | list | |
| summary | text | |
| userNoteText | text | |
| llmRaw | json | |
| photoCount | integer | |
| reviewStatus | string | |
| submitStatus | string | |
| appVersion | string | |

### Trips

| Field | Type | Required |
|---|---|---|
| localTripId | string | yes |
| title | string | yes |
| startedAt | datetime | yes |
| endedAt | datetime | |
| observationLocalIds | list | |
| observationCount | integer | |
| categories | list | |
| subjectSummaries | list | |
| centerLatitude | number | |
| centerLongitude | number | |
| boundingBox | json | |
| totalDistanceEstimateMiles | number | |
| weatherSummary | text | |
| dominantWeatherCondition | string | |
| minTemperatureF | number | |
| maxTemperatureF | number | |
| avgTemperatureF | number | |
| avgBarometricPressureHpa | number | |
| tripSummary | text | |
| habitats | list | |
| notableMoments | list | |
| needsReview | boolean | |
| reviewStatus | string | |
| routeGeoJson | json | |
| appVersion | string | |

## Privacy and Security

- **Exact GPS coordinates** can reveal sensitive wildlife locations. Do not make observation reads public.
- **Token storage** in the browser is convenient but not secret. Users should treat shared machines with caution.
- **Photo metadata** may also contain GPS. The frontend should strip EXIF location before upload if the user chooses.
