#!/usr/bin/env python3
"""
Integration test script to demonstrate the LLM Agent + Message Queue integration.

This script demonstrates:
1. Creating sample events
2. Publishing them to the message queue (simulating what LLM Agent does)
3. Consuming events with the MQ Consumer

Run this script to verify the integration is working correctly.
"""

import sys
import time
import logging
from datetime import datetime
from uuid import uuid4
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from models import FreeFoodEvent
from services.mq import MessageQueue, Consumer

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_sample_events():
    """Create sample food events for testing."""
    return [
        FreeFoodEvent(
            event_id=str(uuid4()),
            title="Free Pizza Night",
            description="CS Club hosting pizza night! Join us for free pizza and coding.",
            location="CS Building Room 150",
            start_time=datetime.now(),
            source="social_media_cs_club",
            llm_confidence=0.95,
            reason="Explicitly mentions 'free pizza'",
            published_at=datetime.now(),
            metadata={
                "club_name": "CS Club",
                "raw_post": "Free pizza at CS club tonight!",
            },
        ),
        FreeFoodEvent(
            event_id=str(uuid4()),
            title="Cultural Showcase",
            description="Celebrate diversity with food and performances!",
            location="Goodell Lawn",
            start_time=datetime.now(),
            source="social_media_cultural_society",
            llm_confidence=0.88,
            reason="Mentions food in event context",
            published_at=datetime.now(),
            metadata={
                "club_name": "Cultural Society",
                "raw_post": "Join us for cultural showcase with dinner!",
            },
        ),
        FreeFoodEvent(
            event_id=str(uuid4()),
            title="Gaming Tournament",
            description="Smash Bros tournament with snacks and drinks",
            location="Student Center",
            start_time=datetime.now(),
            source="social_media_gaming_club",
            llm_confidence=0.92,
            reason="Mentions snacks and drinks provided",
            published_at=datetime.now(),
            metadata={
                "club_name": "Gaming Club",
                "raw_post": "Tournament tonight! Snacks provided!",
            },
        ),
    ]


def test_publish():
    """Test Step 1: Publish sample events to the message queue (simulates LLM Agent)."""
    logger.info("=" * 70)
    logger.info("STEP 1: Testing Event Publishing (LLM Agent Simulation)")
    logger.info("=" * 70)

    mq = MessageQueue()
    events = create_sample_events()

    logger.info(f"Publishing {len(events)} free food events to message queue...")

    for event in events:
        try:
            message_id = mq.publish(event)
            logger.info(f"✅ Published: {event.title}")
            logger.info(f"   Event ID: {event.event_id}")
            logger.info(f"   Location: {event.location}")
            logger.info(f"   Confidence: {event.llm_confidence:.2f}")
            logger.info(f"   Message ID: {message_id}")
            logger.info("")
        except Exception as e:
            logger.error(f"❌ Failed to publish event: {e}")

    mq.close()
    logger.info(f"Successfully published {len(events)} events!\n")
    return len(events)


def test_consume(event_count, timeout=10):
    """Test Step 2: Consume events from the message queue (simulates MQ Consumer)."""
    logger.info("=" * 70)
    logger.info("STEP 2: Testing Event Consumption (MQ Consumer)")
    logger.info("=" * 70)
    logger.info(f"Waiting to receive {event_count} events (timeout: {timeout}s)...\n")

    consumed_count = 0
    start_time = time.time()

    def handle_event(event: FreeFoodEvent):
        nonlocal consumed_count
        consumed_count += 1

        logger.info(f"📨 RECEIVED EVENT #{consumed_count}")
        logger.info(f"   Title: {event.title}")
        logger.info(f"   Location: {event.location}")
        logger.info(f"   Source: {event.source}")
        logger.info(f"   Confidence: {event.llm_confidence:.2f}")
        logger.info(f"   Reason: {event.reason}")

        if event.metadata:
            logger.info(f"   Club: {event.metadata.get('club_name', 'N/A')}")

        logger.info("")

    consumer = Consumer(
        consumer_group="integration_test_group",
        consumer_name=f"test_worker_{int(time.time())}",
    )

    try:
        while consumed_count < event_count:
            # Check timeout
            if time.time() - start_time > timeout:
                logger.warning(
                    f"⚠️  Timeout reached. Only received {consumed_count}/{event_count} events."
                )
                break

            # Try to consume with a shorter block time
            messages = consumer.client.xreadgroup(
                consumer.consumer_group,
                consumer.consumer_name,
                {consumer.stream_name: ">"},
                count=10,
                block=1000,  # 1 second block
            )

            if messages:
                for stream, message_list in messages:
                    for message_id, data in message_list:
                        consumer._process_message(message_id, data, handle_event)

        logger.info("=" * 70)
        logger.info(
            f"CONSUMPTION COMPLETE: Received {consumed_count}/{event_count} events"
        )
        logger.info("=" * 70)

    except KeyboardInterrupt:
        logger.info("\nTest interrupted by user")
    except Exception as e:
        logger.error(f"Error during consumption: {e}")
    finally:
        consumer.close()

    return consumed_count


def main():
    """Run the complete integration test."""
    # NOTE: Not cleaning up the stream to avoid conflicts with running consumers
    # If you need to clean up, stop all consumers first, then run:
    # redis-cli DEL events.free-food

    logger.info("\n" + "=" * 70)
    logger.info("LLM AGENT + MESSAGE QUEUE INTEGRATION TEST")
    logger.info("=" * 70)
    logger.info("This test demonstrates the full event pipeline:")
    logger.info("  LLM Agent → Message Queue → MQ Consumer")
    logger.info("=" * 70 + "\n")

    try:
        # Publish events (simulates LLM Agent processing and publishing)
        event_count = test_publish()

        # Small delay to ensure messages are ready
        time.sleep(1)

        # Consume events (simulates MQ Consumer receiving events)
        consumed = test_consume(event_count, timeout=15)

        # Summary
        print("\n" + "=" * 70)
        print("INTEGRATION TEST SUMMARY")
        print("=" * 70)
        print(f"Events Published: {event_count}")
        print(f"Events Consumed:  {consumed}")

        if consumed == event_count:
            print(
                "Status: ✅ SUCCESS - All events were successfully published and consumed!"
            )
        else:
            print(
                f"Status: ⚠️  PARTIAL - Only {consumed}/{event_count} events were consumed"
            )

        print("=" * 70)

        return 0 if consumed == event_count else 1

    except Exception as e:
        logger.error(f"Integration test failed: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
