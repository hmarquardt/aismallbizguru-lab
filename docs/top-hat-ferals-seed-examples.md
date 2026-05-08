# Top Hat Ferals - Seed Examples

Safe example records for testing and seeding the Top Hat Ferals app.

## Cat

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

## Sighting

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

## Interaction

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