#!/usr/bin/env python3
"""
Script to demonstrate the MQ Consumer working.
First publishes a test event, then shows the consumer receiving it.
"""

import sys
import time
from pathlib import Path
from datetime import datetime
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).parent.parent))

from models import FreeFoodEvent
from services.mq import MessageQueue, Consumer
from services.mq_consumer.__main__ import EventProcessor

print("=" * 70)
print("MQ CONSUMER DEMONSTRATION")
print("=" * 70)
print()

# Step 1: Publish a test event
print("STEP 1: Publishing a test event to the queue...")
mq = MessageQueue()

event = FreeFoodEvent(
    event_id=str(uuid4()),
    title="Test Free Pizza Event",
    description="This is a test event to demonstrate the consumer",
    location="Student Center",
    start_time=datetime.now(),
    source="test_script",
    llm_confidence=0.99,
    reason="Test event",
    published_at=datetime.now(),
)

message_id = mq.publish(event)
print(f"✅ Published event: {event.title}")
print(f"   Message ID: {message_id}")
print()
mq.close()

# Step 2: Start consumer
print("STEP 2: Starting MQ Consumer to receive the event...")
print("(Consumer will run for 5 seconds or until event is received)")
print()

processor = EventProcessor()
consumer = Consumer(
    consumer_group="demo_group", consumer_name=f"demo_worker_{int(time.time())}"
)

events_received = 0
max_wait = 5  # seconds
start_time = time.time()

try:
    while events_received == 0 and (time.time() - start_time) < max_wait:
        messages = consumer.client.xreadgroup(
            consumer.consumer_group,
            consumer.consumer_name,
            {consumer.stream_name: ">"},
            count=10,
            block=1000,
        )

        if messages:
            for stream, message_list in messages:
                for message_id, data in message_list:
                    consumer._process_message(message_id, data, processor.process_event)
                    events_received += 1

    print()
    print("=" * 70)
    if events_received > 0:
        print("✅ SUCCESS: Consumer received and processed the event!")
    else:
        print("⚠️  No events received (queue might be empty)")
    print("=" * 70)

except Exception as e:
    print(f"Error: {e}")
finally:
    consumer.close()
