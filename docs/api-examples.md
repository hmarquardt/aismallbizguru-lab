# API Examples

Health:

```bash
curl https://lab.aismallbizguru.com/api/health
```

List configured apps:

```bash
curl https://lab.aismallbizguru.com/api/apps
```

Create a record:

```bash
curl -X POST https://lab.aismallbizguru.com/api/junk-drawer/notes \
  -H "Authorization: Bearer $LABBOX_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"data":{"title":"First note","body":"Hello"}}'
```

List records:

```bash
curl https://lab.aismallbizguru.com/api/junk-drawer/notes \
  -H "Authorization: Bearer $LABBOX_TOKEN"
```

Upload a file:

```bash
curl -X POST https://lab.aismallbizguru.com/api/junk-drawer/notes/$RECORD_ID/files \
  -H "Authorization: Bearer $LABBOX_TOKEN" \
  -F "file=@example.png;type=image/png"
```
