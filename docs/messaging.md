# 📨 Message Queue Schema (v1.0.0)

This document defines the schema for all messages published and consumed on our project’s message bus.
Every producer **must** publish this JSON.
Every consumer **must** be able to handle it.

The project will be using Redis Streams by default (queue name: `events.free-food`), but this schema is transport-agnostic (designed to be independent of specific technologies or platforms).

---
## 1. JSON Structure

```json
{
  "schema_version": "1.0.0",
  "event_id": "b5f5c8f4-52f1-4b68-a2a1-7757b71a4df0",
  "title": "Free Pizza Night",
  "description": "Join us in the CS building for free pizza and drinks.",
  "location": "CS Building, Room 150",
  "start_time": "2025-11-02T18:00:00Z",
  "source": "umass-calendar",
  "llm_confidence": 0.93,
  "reason": "LLM detected 'free', 'pizza', 'food' in description.",
  "type": "FREE_FOOD_EVENT",
  "published_at": "2025-11-02T14:03:22Z",
  "retries": 0,
  "metadata": {
    "organizer": "ACM",
    "raw_source_id": "cal-2025-11-02-1234"
  }
}
```


### Field Definitions

| Field              | Type                  | Required | Description                                                           |
| ------------------ | --------------------- | -------- | --------------------------------------------------------------------- |
| **schema_version** | string                | ✅        | Schema version, follows semantic versioning (`major.minor.patch`).    |
| **event_id**       | string                | ✅        | Unique, stable identifier (UUID or source ID).                        |
| **title**          | string                | ✅        | Human-readable event name.                                            |
| **description**    | string                | ❌        | Optional text describing the event.                                   |
| **location**       | string                | ❌        | Where the event occurs.                                               |
| **start_time**     | string (ISO-8601 UTC) | ❌        | Event start time (UTC).                                               |
| **source**         | string                | ✅        | Origin of event data — e.g. `umass-calendar`, `manual`, `scraper`.    |
| **llm_confidence** | float (0–1)           | ❌        | Model’s confidence score that this is a free-food event.              |
| **reason**         | string                | ❌        | Brief reason or rationale given by the classifier.                    |
| **type**           | string                | ✅        | Event type classification. Currently `"FREE_FOOD_EVENT"`.             |
| **published_at**   | string (ISO-8601 UTC) | ✅        | When the message was created and published to MQ.                     |
| **retries**        | integer               | ✅        | Retry count for failed processing attempts. Producers start with `0`. |
| **metadata**       | object                | ✅        | Free-form JSON object for additional data. Always `{}`, never `null`. |


### Producer Rules

Producers (like Decision Gateway or LLM Agent) must follow these rules:

1. Must set: schema_version, event_id, title, source, type, published_at, and retries.

2. Must set published_at → current UTC ISO-8601 string (e.g. "2025-11-02T14:03:22Z").

3. Must set retries → 0.

4. Should include llm_confidence and reason if available.

5. Must not introduce new top-level fields without updating this file and bumping schema_version.

```python
from datetime import datetime, timezone
from uuid import uuid4

def build_free_food_message(raw_event: dict) -> dict:
    return {
        "schema_version": "1.0.0",
        "event_id": raw_event.get("id") or str(uuid4()),
        "title": raw_event["title"],
        "description": raw_event.get("description"),
        "location": raw_event.get("location"),
        "start_time": raw_event.get("start_time"),
        "source": raw_event.get("source", "unknown"),
        "llm_confidence": raw_event.get("llm_confidence"),
        "reason": raw_event.get("reason"),
        "type": "FREE_FOOD_EVENT",
        "published_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "retries": 0,
        "metadata": raw_event.get("metadata") or {},
    }
```

### Consumer Rules

Consumers (like MQ Consumer or Notification Service) must:

1. Parse JSON safely and validate against this schema.

2. Tolerate missing optional fields.

3. Never remove or rename fields when re-publishing.

4. May only modify:

   - retries (increment by 1 on failure)

   - metadata (e.g. add "last_error").

```python
def on_processing_error(msg: dict, error_msg: str) -> dict:
    msg["retries"] = msg.get("retries", 0) + 1
    msg.setdefault("metadata", {})
    msg["metadata"]["last_error"] = error_msg
    return msg
```

### Versioning

| Change type                | Example                     | Version bump |
| -------------------------- | --------------------------- | ------------ |
| Add optional field         | add `"tags"`                | `1.0.1`      |
| Remove or rename field     | rename `"title"` → `"name"` | `1.1.0`      |
| Structural/breaking change | overhaul format             | `2.0.0`      |

Consumers must log a warning if schema_version major number differs:

```python
if msg["schema_version"].split(".")[0] != "1":
    logger.warning(f"Unsupported schema version: {msg['schema_version']}")
```

### Data Format Conventions

* IDs: strings (UUID preferred)

* Times: UTC ISO-8601 ending in "Z"

* Confidence: float between 0 and 1

* Metadata: always a JSON object ({} if empty)

### Python Model

The following code is in models.py, All services must import this model, not redefine it:

```python
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field

class FreeFoodEvent(BaseModel):
    schema_version: str = "1.0.0"
    event_id: str
    title: str
    description: Optional[str] = None
    location: Optional[str] = None
    start_time: Optional[datetime] = None
    source: str
    llm_confidence: Optional[float] = Field(default=None, ge=0, le=1)
    reason: Optional[str] = None
    type: str = "FREE_FOOD_EVENT"
    published_at: datetime
    retries: int = 0
    metadata: dict[str, Any] = {}
```

Producers → publish FreeFoodEvent objects

Consumers → validate, process, retry if needed

Everyone → keep docs/messaging.md in sync with any change
