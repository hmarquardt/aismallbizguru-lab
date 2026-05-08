# Cursor / Opencode Prompt: Configure LabBox Backend for Top Hat Ferals TNG

## Goal

You are working in the existing `hmarquardt/aismallbizguru-lab` repository.

Configure LabBox to support the new static frontend:

```text
thf_tng.html
```

for Top Hat Ferals.

The frontend will have:

- Public read-only display.
- Admin tab with bearer-token writes.
- Local browser storage of the bearer token.
- Ability to add cats, sightings, and interactions.
- Ability to upload images, especially for interactions.

---

## Important Security Rules

- Public reads may be unauthenticated.
- Writes must require bearer token.
- Do not make write endpoints public.
- Do not hard-code any bearer token.
- Do not commit `.env`.
- Do not commit real secrets.
- `.env.example` may contain placeholders only.
- CORS must allow the Top Hat Ferals public frontend origin.

---

## Target App

```text
top-hat-ferals
```

---

## Target API Base

```text
https://lab.aismallbizguru.com/api
```

---

## Static Frontend Origins

Support these CORS origins if applicable:

```text
https://hmarquardt.github.io
https://tophatferals.com
https://www.tophatferals.com
```

If the actual published origin differs, add that too.

---

## Resource Simplification

Do not create `new-arrivals` as a separate resource.

Use only:

```text
cats
sightings
interactions
```

New arrivals are represented as:

```text
cats.status = "new"
```

or tags:

```json
["new-arrival"]
```

---

## Task 1: Inspect Existing Backend

Open and inspect:

```text
config/apps.yaml
.env.example
docs/
backend settings/CORS code
config loader
record routes
file upload routes
auth/token handling
```

Do not redesign the backend.

---

## Task 2: Update `config/apps.yaml`

Add or update this app:

```yaml
top-hat-ferals:
  title: Top Hat Ferals
  description: Public observational log for the Top Hat Road feral cat colony.
  auth:
    default_read: public
    default_write: token

  resources:
    cats:
      label: Cats
      fields:
        name:
          type: string
          required: true
        nickname:
          type: string
        status:
          type: string
        description:
          type: text
        notes:
          type: text
        photo_url:
          type: string
        photo:
          type: string
        image:
          type: string
        first_seen:
          type: datetime
        last_seen:
          type: datetime
        color:
          type: string
        markings:
          type: text
        temperament:
          type: string
        tags:
          type: list
      files:
        enabled: true
        allowed_types:
          - image/png
          - image/jpeg
          - image/webp
        max_size_mb: 25

    sightings:
      label: Sightings
      fields:
        cat:
          type: string
          required: true
        cat_name:
          type: string
        cat_id:
          type: string
        date:
          type: datetime
          required: true
        time:
          type: string
        location:
          type: string
        note:
          type: text
        notes:
          type: text
        description:
          type: text
        photo_url:
          type: string
        photo:
          type: string
        image:
          type: string
        confidence:
          type: string
        source:
          type: string
        tags:
          type: list
      files:
        enabled: true
        allowed_types:
          - image/png
          - image/jpeg
          - image/webp
        max_size_mb: 25

    interactions:
      label: Interactions
      fields:
        cat:
          type: string
          required: true
        cat_name:
          type: string
        cat_id:
          type: string
        date:
          type: datetime
          required: true
        type:
          type: string
        location:
          type: string
        with:
          type: string
        note:
          type: text
        notes:
          type: text
        description:
          type: text
        photo_url:
          type: string
        photo:
          type: string
        image:
          type: string
        tags:
          type: list
      files:
        enabled: true
        allowed_types:
          - image/png
          - image/jpeg
          - image/webp
        max_size_mb: 25
```

---

## Task 3: Verify Public Read / Token Write Behavior

Confirm the backend supports this behavior:

```text
GET /api/top-hat-ferals/cats              public
GET /api/top-hat-ferals/sightings         public
GET /api/top-hat-ferals/interactions      public

POST /api/top-hat-ferals/cats             bearer token required
POST /api/top-hat-ferals/sightings        bearer token required
POST /api/top-hat-ferals/interactions     bearer token required
```

If current code does not support `auth.default_read: public` and `auth.default_write: token`, implement the smallest safe change needed.

Do not make all apps public. Only honor app/resource config.

---

## Task 4: Verify File Upload Support

Confirm or implement file upload support for:

```text
POST /api/top-hat-ferals/cats/{record_id}/files
POST /api/top-hat-ferals/sightings/{record_id}/files
POST /api/top-hat-ferals/interactions/{record_id}/files
```

Writes/file uploads must require bearer token.

Interactions must support image uploads.

Allowed content types:

```text
image/png
image/jpeg
image/webp
```

Max size:

```text
25 MB
```

If the backend already has a generic file upload route, configure it.

If not, implement the smallest generic route that works with the existing records/files system.

---

## Task 5: CORS

Ensure CORS allows the static frontend origins:

```text
https://hmarquardt.github.io
https://tophatferals.com
https://www.tophatferals.com
```

If using `.env.example`, update it with placeholder/example value:

```env
CORS_ALLOW_ORIGINS=https://hmarquardt.github.io,https://tophatferals.com,https://www.tophatferals.com
```

Do not put secrets in `.env.example`.

---

## Task 6: Admin Token Instructions

Add docs explaining how to create a bearer token for Top Hat Ferals admin writes.

The token should have scopes allowing write/files access to:

```json
{"top-hat-ferals": ["read", "write"]}
```

Use whatever scope format the backend already supports. In this repo, scopes are app-level JSON. Do not document per-resource scope strings unless the backend is changed to support them.

---

## Task 7: Add Docs

Create:

```text
docs/top-hat-ferals.md
```

Include:

- App ID: `top-hat-ferals`
- Resources:
  - `cats`
  - `sightings`
  - `interactions`
- Explanation that `new-arrivals` are represented by status/tag, not a separate resource.
- Public read endpoints.
- Token-protected write endpoints.
- Token-protected file upload endpoints.
- CORS origins.
- How to create a bearer token.
- How to enter the token in `thf_tng.html` Admin tab.
- Warning not to use the Admin tab on shared/public computers.
- How to clear the token from the browser.
- How to test with curl.
- Restart command after config changes.

---

## Task 8: Add Seed Examples

Create:

```text
docs/top-hat-ferals-seed-examples.md
```

Include one safe example each.

### Cat

```json
{
  "data": {
    "name": "Top Hat",
    "nickname": "Hatty",
    "status": "active",
    "description": "Black and white cat with tuxedo markings.",
    "color": "black and white",
    "temperament": "cautious but curious",
    "tags": ["regular", "feeding-station"]
  }
}
```

### Sighting

```json
{
  "data": {
    "cat": "Top Hat",
    "date": "2026-05-08",
    "time": "dusk",
    "location": "Feeding station",
    "note": "Appeared just after dusk and checked the bowl.",
    "confidence": "high",
    "source": "admin",
    "tags": ["evening", "feeding"]
  }
}
```

### Interaction

```json
{
  "data": {
    "cat": "Top Hat",
    "date": "2026-05-08",
    "type": "feeding",
    "location": "Feeding station",
    "with": "Hank",
    "note": "Came close enough to inspect the food bowl while I was nearby.",
    "tags": ["feeding", "progress"]
  }
}
```

---

## Task 9: Curl Examples

Add examples to `docs/top-hat-ferals.md`.

Public read:

```bash
curl https://lab.aismallbizguru.com/api/top-hat-ferals/cats
curl https://lab.aismallbizguru.com/api/top-hat-ferals/sightings
curl https://lab.aismallbizguru.com/api/top-hat-ferals/interactions
```

Create cat:

```bash
curl -X POST https://lab.aismallbizguru.com/api/top-hat-ferals/cats   -H "Authorization: Bearer $LABBOX_THF_TOKEN"   -H "Content-Type: application/json"   -d '{
    "data": {
      "name": "Top Hat",
      "status": "active",
      "description": "Black and white cat with tuxedo markings.",
      "tags": ["regular"]
    }
  }'
```

Create interaction:

```bash
curl -X POST https://lab.aismallbizguru.com/api/top-hat-ferals/interactions   -H "Authorization: Bearer $LABBOX_THF_TOKEN"   -H "Content-Type: application/json"   -d '{
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

File upload example:

```bash
curl -X POST https://lab.aismallbizguru.com/api/top-hat-ferals/interactions/RECORD_ID/files   -H "Authorization: Bearer $LABBOX_THF_TOKEN"   -F "file=@cat-photo.jpg"
```

Use `RECORD_ID` as a placeholder only.

---

## Task 10: Restart / Deploy Notes

Document restart command:

```bash
cd /opt/labbox
docker compose up -d --build api worker
```

Then test:

```bash
curl https://lab.aismallbizguru.com/api/top-hat-ferals/cats
curl https://lab.aismallbizguru.com/api/top-hat-ferals/sightings
curl https://lab.aismallbizguru.com/api/top-hat-ferals/interactions
```

---

## Validation

Run tests if available:

```bash
python -m pytest
```

If tests fail for unrelated existing reasons, report clearly.

Validate config loads using the project’s existing mechanism.

---

## Deliverables

Expected changed/created files:

```text
config/apps.yaml
.env.example
docs/top-hat-ferals.md
docs/top-hat-ferals-seed-examples.md
```

Possibly changed if required:

```text
backend CORS/settings files
backend auth/permission files
backend file upload route files
```

---

## Final Report

Report:

- Files changed.
- Whether public reads work.
- Whether token writes work.
- Whether interaction image uploads work.
- CORS origins configured.
- Restart command.
- Any assumptions or TODOs.
