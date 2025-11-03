#!/usr/bin/env python3
"""Example demonstrating message queue usage for publishing and consuming events."""

from datetime import datetime, timezone
from uuid import uuid4
from models import FreeFoodEvent
from services.mq import MessageQueue, Consumer


def publish_example():
    """Example: Publishing an event to the message queue."""
    mq = MessageQueue()

    event = FreeFoodEvent(
        event_id=str(uuid4()),
        title="Free Pizza Night",
        description="Join us in the CS building for free pizza",
        location="CS Building, Room 150",
        start_time=datetime.now(timezone.utc),
        source="example-script",
        llm_confidence=0.95,
        reason="Contains keywords: free, pizza",
        published_at=datetime.now(timezone.utc),
    )

    message_id = mq.publish(event)
    print(f"Published event: {event.event_id}, Message ID: {message_id}")

    mq.close()


def consume_example():
    """Example: Consuming events from the message queue."""

    def handle_event(event: FreeFoodEvent):
        print(f"Received event: {event.title} at {event.location}")
        print(f"Event ID: {event.event_id}, Source: {event.source}")

    consumer = Consumer(consumer_group="example_group", consumer_name="example_worker")

    try:
        consumer.consume(handle_event)
    finally:
        consumer.close()


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python example_mq_usage.py [publish|consume]")
        sys.exit(1)

    command = sys.argv[1]

    if command == "publish":
        publish_example()
    elif command == "consume":
        consume_example()
    else:
        print(f"Unknown command: {command}")
        print("Usage: python example_mq_usage.py [publish|consume]")
        sys.exit(1)
