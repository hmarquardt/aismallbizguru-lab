# App Config

LabBox apps are configured in `config/apps.yaml`.

Example:

```yaml
apps:
  junk-drawer:
    title: Junk Drawer
    description: General-purpose scratchpad app.
    auth:
      default_read: public
      default_write: token
    resources:
      notes:
        label: Notes
        fields:
          title:
            type: string
            required: true
          body:
            type: text
          tags:
            type: list
        files:
          enabled: true
          allowed_types:
            - image/png
            - image/jpeg
          max_size_mb: 25
```

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

Config validates at app startup. Unknown apps or resources return API errors instead of silently creating data.

Set `default_read: public` only for data that can be fetched directly from public browser clients. Writes remain token-protected with `default_write: token`.
