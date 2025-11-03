# Message Queue Usage Guide

## Overview

The project uses Redis Streams for asynchronous message passing between microservices. The implementation is in `services/mq.py` with two main classes:

- **MessageQueue**: For publishing events
- **Consumer**: For consuming events

## Quick Start

### Publishing Events

```python
from datetime import datetime, timezone
from uuid import uuid4
from models import FreeFoodEvent
from services.mq import MessageQueue

mq = MessageQueue()

event = FreeFoodEvent(
    event_id=str(uuid4()),
    title="Free Pizza Night",
    description="Join us for free pizza",
    location="CS Building, Room 150",
    source="my-service",
    published_at=datetime.now(timezone.utc),
)

message_id = mq.publish(event)
mq.close()
```

### Consuming Events

```python
from models import FreeFoodEvent
from services.mq import Consumer

def handle_event(event: FreeFoodEvent):
    print(f"Processing: {event.title}")

consumer = Consumer(
    consumer_group="my-service",
    consumer_name="worker-1"
)

consumer.consume(handle_event)
consumer.close()
```

## MessageQueue Class

### Constructor

```python
MessageQueue(redis_url: str = REDIS_URL, stream_name: str = MQ_STREAM)
```

### Methods

- `publish(event: FreeFoodEvent) -> str`: Publishes event to Redis Stream, returns message ID
- `close()`: Closes Redis connection

## Consumer Class

### Constructor

```python
Consumer(
    redis_url: str = REDIS_URL,
    stream_name: str = MQ_STREAM,
    consumer_group: str = "default",
    consumer_name: str = "worker"
)
```

### Methods

- `consume(handler: Callable[[FreeFoodEvent], None], block: int = 5000, count: int = 10)`: Starts consuming messages
  - `handler`: Function that processes each event
  - `block`: Milliseconds to wait for new messages (default 5000)
  - `count`: Max messages to read per batch (default 10)
- `close()`: Closes Redis connection

## Features

- Automatic consumer group creation
- Schema version validation
- Message acknowledgment after successful processing
- Error logging without crashing
- Graceful shutdown on KeyboardInterrupt

## Example Script

Run the example script:

```bash
# Publish a test event
poetry run python scripts/example_mq_usage.py publish

# Consume events (runs continuously)
poetry run python scripts/example_mq_usage.py consume
```

## Integration into Services

### Decision Gateway / LLM Agent (Producers)

```python
from services.mq import MessageQueue

mq = MessageQueue()
event = build_event(...)
mq.publish(event)
```

### MQ Consumer / Notification Service (Consumers)

```python
from services.mq import Consumer

def process_event(event: FreeFoodEvent):
    # Your processing logic
    pass

consumer = Consumer(
    consumer_group="notification-service",
    consumer_name="worker-1"
)
consumer.consume(process_event)
```

## Redis Stream Details

- Stream name: `events.free-food` (configurable via `MQ_STREAM` env var)
- Messages stored as JSON in `data` field
- Uses consumer groups for distributed processing
- Multiple consumers can process different messages in parallel
