# API Examples

Health:

```bash
curl https://labs.smallbizguru.com/api/health
```

List configured apps:

```bash
curl https://labs.smallbizguru.com/api/apps
```

Create a record:

```bash
curl -X POST https://labs.smallbizguru.com/api/junk-drawer/notes \
  -H "Authorization: Bearer $LABBOX_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"data":{"title":"First note","body":"Hello"}}'
```

List records:

```bash
curl https://labs.smallbizguru.com/api/junk-drawer/notes \
  -H "Authorization: Bearer $LABBOX_TOKEN"
```

Upload a file:

```bash
curl -X POST https://labs.smallbizguru.com/api/junk-drawer/notes/$RECORD_ID/files \
  -H "Authorization: Bearer $LABBOX_TOKEN" \
  -F "file=@example.png;type=image/png"
```
