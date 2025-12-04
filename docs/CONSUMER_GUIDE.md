# MQ Consumer Usage Guide

## How the MQ Consumer Works

The MQ Consumer (`services/mq_consumer`) is a **long-running service** that continuously monitors the message queue for new events. When you run it, it will:

1. **Start up** and display startup messages
2. **Wait for events** (blocking, appears to "hang")
3. **Process events** as they arrive from the queue
4. **Keep running** until you stop it with Ctrl+C

When you run:
```bash
poetry run python -m services.mq_consumer
```

You'll see startup messages like:
```
2025-12-03 21:31:24,906 - services.mq_consumer.__main__ - INFO - Starting MQ Consumer Service...
2025-12-03 21:31:24,906 - services.mq_consumer.__main__ - INFO - Redis URL: redis://localhost:6379/0
2025-12-03 21:31:24,906 - services.mq_consumer.__main__ - INFO - Stream: events.free-food
2025-12-03 21:31:24,906 - services.mq - INFO - Created consumer group mq_consumer_group
2025-12-03 21:31:24,906 - services.mq_consumer.__main__ - INFO - Consumer ready. Waiting for events...
2025-12-03 21:31:24,906 - services.mq - INFO - Starting consumer mq_consumer_worker on events.free-food
```

Then it **waits silently** for events to arrive. This is normal! It's listening to the queue.

## How to Test the Consumer

### Option 1: Quick Test Script (Recommended)

Run the test script that publishes an event and shows the consumer processing it:

```bash
poetry run python scripts/test_consumer.py
```

**Output:**
```
======================================================================
MQ CONSUMER DEMONSTRATION
======================================================================

STEP 1: Publishing a test event to the queue...
✅ Published event: Test Free Pizza Event
   Message ID: 1764815484898-0

STEP 2: Starting MQ Consumer to receive the event...
2025-12-03 21:31:24,908 - INFO - Processing event: 7a67... | Title: Test Free Pizza Event
2025-12-03 21:31:24,908 - INFO - High confidence event (0.99)
2025-12-03 21:31:24,909 - INFO - Successfully processed event. Total processed: 1

✅ SUCCESS: Consumer received and processed the event!
```

### Option 2: Manual Two-Terminal Test

**Terminal 1 - Start the Consumer:**
```bash
poetry run python -m services.mq_consumer
```

You'll see:
```
INFO - Starting MQ Consumer Service...
INFO - Consumer ready. Waiting for events...
INFO - Starting consumer mq_consumer_worker on events.free-food
```

**Terminal 2 - Publish Events:**
```bash
# Option A: Use integration demo
poetry run python scripts/integration_demo.py

# Option B: Use LLM Agent with real data
poetry run python -m services.llm_agent --csv sample_events.csv

# Option C: Use example script
poetry run python scripts/example_mq_usage.py publish
```

**Back to Terminal 1:**

You'll now see the consumer processing events in real-time:
```
INFO - Processing event: abc123 | Title: Free Pizza Night | Location: CS Building
INFO - High confidence event (0.95): abc123
INFO - Classification reason: Explicitly mentions 'free pizza'
INFO - Successfully processed event abc123. Total processed: 1
```

### Option 3: End-to-End Integration Demo

Run the full pipeline demonstration:
```bash
poetry run python scripts/integration_demo.py
```

This shows:
- LLM Agent publishing events to the queue
- Consumer receiving and processing them

## What Output to Expect

### When Consumer Starts:
```
INFO - Starting MQ Consumer Service...
INFO - Redis URL: redis://localhost:6379/0
INFO - Stream: events.free-food
INFO - Created consumer group mq_consumer_group
INFO - Consumer ready. Waiting for events...
INFO - Starting consumer mq_consumer_worker on events.free-food
```

### When an Event Arrives:
```
INFO - Processing event: <event_id> | Title: <title> | Location: <location> | Source: <source>
INFO - High confidence event (0.95): <event_id>
INFO - Classification reason: <reason>
INFO - Event starts at: <datetime>
INFO - Processing latency: 0.123s
INFO - Successfully processed event <event_id>. Total processed: 1
```

### When You Stop It (Ctrl+C):
```
INFO - Shutting down gracefully...
INFO - Final statistics: {'events_processed': 5, 'events_failed': 0, ...}
INFO - MQ Consumer Service stopped.
```

## Common Issues

### "Nothing happens after startup"
✅ **This is normal!** The consumer is waiting for events. Publish some events from another terminal.

### "Consumer not receiving events"
Check:
1. Redis is running: `redis-cli ping`
2. Events are in the queue: `redis-cli XLEN events.free-food`
3. Consumer group exists: `redis-cli XINFO GROUPS events.free-food`

### "Want to see it process events immediately"
Run the quick test: `poetry run python scripts/test_consumer.py`

## Stopping the Consumer

Press **Ctrl+C** in the terminal where the consumer is running. You'll see:
```
INFO - Shutting down gracefully...
INFO - Final statistics: {...}
INFO - MQ Consumer Service stopped.
```

In production, the MQ Consumer would run as:
- A background service (systemd, supervisor, etc.)
- A Docker container (always running)
- A Kubernetes deployment

For development, run it in a dedicated terminal window while testing your LLM Agent.
