# Top Hat Ferals

Public observational log for the Top Hat Road feral cat colony.

**App ID:** `top-hat-ferals`

**API Base:** `https://lab.aismallbizguru.com/api`

## Resources

- `cats` - Cat profiles
- `sightings` - Observation records
- `interactions` - Human-cat interactions

**Note:** There is no separate `new-arrivals` resource. Use `cats.status = "new"` or `cats.tags = ["new-arrival"]` to mark new cats.

## Public Endpoints (No Auth Required)

```
GET https://lab.aismallbizguru.com/api/top-hat-ferals/cats
GET https://lab.aismallbizguru.com/api/top-hat-ferals/sightings
GET https://lab.aismallbizguru.com/api/top-hat-ferals/interactions
```

## Token-Protected Endpoints

Writes require a bearer token with appropriate scopes.

```
POST https://lab.aismallbizguru.com/api/top-hat-ferals/cats
POST https://lab.aismallbizguru.com/api/top-hat-ferals/sightings
POST https://lab.aismallbizguru.com/api/top-hat-ferals/interactions
```

## File Uploads

Upload images to any record:

```
POST https://lab.aismallbizguru.com/api/top-hat-ferals/cats/{record_id}/files
POST https://lab.aismallbizguru.com/api/top-hat-ferals/sightings/{record_id}/files
POST https://lab.aismallbizguru.com/api/top-hat-ferals/interactions/{record_id}/files
```

Allowed types: `image/png`, `image/jpeg`, `image/webp`
Max size: 25 MB

## CORS Origins

The API allows requests from:
- `https://hmarquardt.github.io`
- `https://tophatferals.com`
- `https://www.tophatferals.com`

## Creating a Bearer Token

Use `Admin -> Tokens` in LabBox and create a token with this scopes JSON:

```json
{"top-hat-ferals": ["read", "write"]}
```

Use read-only scope only when a token should not be able to create, update, delete, or upload:

```json
{"top-hat-ferals": ["read"]}
```

## Using the Admin Tab in thf_tng.html

1. Go to the Admin tab
2. Enter your bearer token in the token field
3. The token is stored in local browser storage
4. Use the admin forms to add cats, sightings, and interactions

**Security Warning:** Do not use the Admin tab on shared or public computers. Clear the token when done by using the "Clear Token" button or by clearing browser local storage.

To clear the token from local storage:
```javascript
localStorage.removeItem('labbox_token');
```

## Testing with curl

Public read:
```bash
curl https://lab.aismallbizguru.com/api/top-hat-ferals/cats
curl https://lab.aismallbizguru.com/api/top-hat-ferals/sightings
curl https://lab.aismallbizguru.com/api/top-hat-ferals/interactions
```

Public read from the Top Hat Ferals origin:

```bash
curl -i -sS https://lab.aismallbizguru.com/api/top-hat-ferals/cats \
  -H "Origin: https://tophatferals.com"
```

Create a cat:
```bash
curl -X POST https://lab.aismallbizguru.com/api/top-hat-ferals/cats \
  -H "Authorization: Bearer $LABBOX_THF_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "data": {
      "name": "Top Hat",
      "status": "active",
      "description": "Black and white cat with tuxedo markings.",
      "tags": ["regular"]
    }
  }'
```

Create an interaction:
```bash
curl -X POST https://lab.aismallbizguru.com/api/top-hat-ferals/interactions \
  -H "Authorization: Bearer $LABBOX_THF_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "data": {
      "cat": "Top Hat",
      "date": "2026-05-08",
      "type": "feeding",
      "location": "Feeding station",
      "note": "Came by for food around dusk.",
      "tags": ["feeding"]
    }
  }'
```

Upload a file:
```bash
curl -X POST https://lab.aismallbizguru.com/api/top-hat-ferals/interactions/RECORD_ID/files \
  -H "Authorization: Bearer $LABBOX_THF_TOKEN" \
  -F "file=@cat-photo.jpg"
```

Replace `RECORD_ID` with the actual record ID and `$LABBOX_THF_TOKEN` with your bearer token.

## Restart After Config Changes

```bash
cd /opt/labbox
docker compose up -d --build api worker
```

## Verify Endpoints

After restart, verify the public endpoints work:

```bash
curl https://lab.aismallbizguru.com/api/top-hat-ferals/cats
curl https://lab.aismallbizguru.com/api/top-hat-ferals/sightings
curl https://lab.aismallbizguru.com/api/top-hat-ferals/interactions
```
