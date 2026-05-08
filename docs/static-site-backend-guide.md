# Using LabBox as a Static Site Backend

LabBox can back simple static sites, including a single-page site hosted on GitHub Pages. The static page is only the frontend. LabBox is the API, database, file store, admin console, and backup target.

Production API base URL:

```text
https://lab.aismallbizguru.com/api
```

## Mental Model

LabBox organizes data like this:

```text
Project app -> Resource/table -> Record/row -> Files/objects
```

Example:

```text
portfolio -> projects -> one project record -> screenshots, PDFs, JSON files
```

In config terms:

- An app is a project or product namespace.
- A resource is a table-like collection inside that project.
- A field defines the shape of records in that resource.
- A record is one JSON document stored in SQLite.
- A file is object storage metadata in SQLite plus bytes in MinIO.

The admin UI is generated from `config/apps.yaml`. The API validates incoming records against that same config.

## Important Browser Security Rule

A GitHub Pages site is public JavaScript. Any API token placed in that JavaScript is public too.

Use one of these patterns:

- Public read-only site: expose only data that is safe to read publicly, once the backend supports public read/CORS for that use case.
- Private/admin tool: require login or keep the tool behind a trusted environment.
- Write-capable public form: use a small server-side proxy/function to hold the LabBox token, validate input, and call LabBox from the server.
- Personal tool with a manually pasted token: acceptable for internal experiments, but not for public pages.

Current state: record and file API routes require a bearer token, and the backend does not yet configure CORS. A browser page hosted at `*.github.io` will need CORS support before it can call LabBox directly.

## Creating a New Project

Projects are configured in [config/apps.yaml](../config/apps.yaml).

Add a new top-level entry under `apps`:

```yaml
apps:
  portfolio:
    title: Portfolio
    description: Public portfolio content managed from LabBox.
    auth:
      default_read: private
      default_write: token
    resources:
      projects:
        label: Projects
        fields:
          title:
            type: string
            required: true
          summary:
            type: text
          url:
            type: string
          featured:
            type: boolean
          tags:
            type: list
        files:
          enabled: true
          allowed_types:
            - image/png
            - image/jpeg
            - application/pdf
          max_size_mb: 25
```

After editing config, restart the API so LabBox reloads the app registry and syncs configured apps into SQLite.

```bash
docker compose up -d --build api worker
```

On the VPS:

```bash
ssh root@lab.aismallbizguru.com 'cd /opt/labbox && docker compose up -d --build api worker'
```

## Field Types

Supported field types:

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

Practical guidance:

- Use `string` for short single-line values.
- Use `text` for long copy.
- Use `boolean` for toggles.
- Use `list` for arrays like tags. In the admin form, enter JSON such as `["a", "b"]`.
- Use `json` for structured nested data when the shape is not worth modeling as separate resources yet.
- Use separate resources when the objects need their own lifecycle, list page, files, or permissions.

## Tables and Objects

LabBox does not create one SQLite table per resource. It uses generic tables:

- `apps`: configured project metadata
- `records`: JSON records for all app resources
- `files`: object metadata for uploaded files
- `api_tokens`: hashed API tokens
- `backup_runs`: backup history

Resource names behave like logical tables:

```text
records where app_id = "portfolio" and resource = "projects"
```

This keeps the backend flexible. You add new project objects by changing YAML, not by writing migrations for every new table.

## Admin Workflow

After a project is configured:

1. Open `https://lab.aismallbizguru.com/admin/login`.
2. Go to `Apps`.
3. Click the resource link, such as `Projects`.
4. Create records with `New Record`.
5. Open a record detail page to edit/delete it.
6. Upload, download, rename, or delete files attached to that record.

File rename changes the displayed filename metadata. The object key remains stable in storage.

## API Workflow

Create an API token from `Admin -> Tokens`.

Use scoped JSON such as:

```json
{"portfolio": ["read", "write"]}
```

Or read-only:

```json
{"portfolio": ["read"]}
```

Create a record:

```bash
curl -X POST https://lab.aismallbizguru.com/api/portfolio/projects \
  -H "Authorization: Bearer $LABBOX_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"data":{"title":"Website Refresh","summary":"New landing page","featured":true,"tags":["web","client"]}}'
```

List records:

```bash
curl https://lab.aismallbizguru.com/api/portfolio/projects \
  -H "Authorization: Bearer $LABBOX_TOKEN"
```

Update a record:

```bash
curl -X PATCH https://lab.aismallbizguru.com/api/portfolio/projects/$RECORD_ID \
  -H "Authorization: Bearer $LABBOX_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"data":{"title":"Website Refresh","summary":"Updated copy","featured":false,"tags":["web"]}}'
```

Delete a record:

```bash
curl -X DELETE https://lab.aismallbizguru.com/api/portfolio/projects/$RECORD_ID \
  -H "Authorization: Bearer $LABBOX_TOKEN"
```

Upload a file:

```bash
curl -X POST https://lab.aismallbizguru.com/api/portfolio/projects/$RECORD_ID/files \
  -H "Authorization: Bearer $LABBOX_TOKEN" \
  -F "file=@screenshot.png;type=image/png"
```

Download a file:

```bash
curl https://lab.aismallbizguru.com/api/files/$FILE_ID \
  -H "Authorization: Bearer $LABBOX_TOKEN" \
  -o file.bin
```

## GitHub Pages Example

This is the shape of a direct browser call once CORS and the chosen auth model are in place:

```html
<script>
const API_BASE = "https://lab.aismallbizguru.com/api";

async function loadProjects() {
  const response = await fetch(`${API_BASE}/portfolio/projects`, {
    headers: {
      Authorization: `Bearer ${window.LABBOX_TOKEN}`
    }
  });

  if (!response.ok) {
    throw new Error(`LabBox request failed: ${response.status}`);
  }

  const payload = await response.json();
  return payload.records;
}
</script>
```

For a public GitHub Pages page, do not hard-code `window.LABBOX_TOKEN` in the repo. Prefer a public-read API mode or a small server-side proxy.

## Recommended First Static Site Setup

For the first GitHub Pages integration, use this architecture:

```text
GitHub Pages
  -> static HTML/CSS/JS
  -> server-side proxy or future public-read LabBox route
  -> LabBox API
  -> SQLite records and MinIO files
```

Build order:

1. Define the project and resources in `config/apps.yaml`.
2. Create sample records in the admin UI.
3. Confirm the API response shape with `curl`.
4. Add CORS/public-read support or create a small proxy.
5. Fetch records from the static page.
6. Add file rendering once record listing is stable.

## When to Create Another Resource

Create another resource when:

- The object has a different set of fields.
- It needs a separate admin list.
- It has its own attached files.
- It should be queried independently.
- It may need different token scopes later.

Example project:

```yaml
apps:
  client-portal:
    title: Client Portal
    resources:
      clients:
        label: Clients
        fields:
          name:
            type: string
            required: true
          email:
            type: string
      invoices:
        label: Invoices
        fields:
          client_id:
            type: string
            required: true
          amount:
            type: number
            required: true
          paid:
            type: boolean
        files:
          enabled: true
          allowed_types:
            - application/pdf
          max_size_mb: 10
```

Use IDs in fields, such as `client_id`, when one resource references another. LabBox does not currently enforce foreign keys between logical resources.

## Current Limitations to Know

- Browser CORS support needs to be added before GitHub Pages can call the API directly.
- Static sites cannot keep bearer tokens secret.
- Logical resources are config-driven, not physical SQLite tables.
- Records are JSON documents; field validation is intentionally lightweight.
- File delete removes the object from storage and soft-deletes metadata.
- Record delete is a soft delete.
