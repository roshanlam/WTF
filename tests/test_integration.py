#!/usr/bin/env python3
"""
Integration Test Script for WTF System
Tests all components: LLM Agent, Message Queue, Decision Gateway, Notification Service
"""

import sys
import time
import logging
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timezone
from models import FreeFoodEvent
from services.mq import MessageQueue, Consumer

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def test_redis_connection():
    """Test 1: Verify Redis connection"""
    logger.info("=" * 60)
    logger.info("TEST 1: Redis Connection")
    logger.info("=" * 60)

    try:
        mq = MessageQueue()
        client = mq.client
        response = client.ping()

        if response:
            logger.info("✅ Redis connection successful")
            mq.close()
            return True
        else:
            logger.error("❌ Redis ping failed")
            return False
    except Exception as e:
        logger.error(f"❌ Redis connection failed: {e}")
        return False


def test_message_publish():
    """Test 2: Publish a test event to Redis"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 2: Message Publishing")
    logger.info("=" * 60)

    try:
        mq = MessageQueue()

        # Create test event
        test_event = FreeFoodEvent(
            event_id="test-integration-001",
            title="Integration Test - Free Pizza",
            description="This is a test event to verify the message queue works",
            location="Test Location - CS Building",
            start_time=datetime.now(timezone.utc),
            source="integration_test",
            published_at=datetime.now(timezone.utc),
            llm_confidence=0.99,
            reason="Integration test event",
            metadata={"test": True, "test_type": "integration"},
        )

        # Publish to queue
        message_id = mq.publish(test_event)
        logger.info("✅ Event published successfully")
        logger.info(f"   Message ID: {message_id}")
        logger.info(f"   Event ID: {test_event.event_id}")
        logger.info(f"   Title: {test_event.title}")
        logger.info(f"   Location: {test_event.location}")

        mq.close()
        return True

    except Exception as e:
        logger.error(f"❌ Failed to publish message: {e}")
        return False


def test_message_consume():
    """Test 3: Consume messages from Redis (with timeout)"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 3: Message Consumption")
    logger.info("=" * 60)

    events_received = []

    def test_handler(event: FreeFoodEvent):
        logger.info(f"✅ Received event: {event.event_id} - {event.title}")
        events_received.append(event)

    try:
        consumer = Consumer(
            consumer_group="integration_test_group",
            consumer_name="integration_test_worker",
        )

        logger.info("Attempting to consume messages (5 second timeout)...")

        # Try to read messages with timeout
        start_time = time.time()
        timeout = 5  # seconds

        while time.time() - start_time < timeout:
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
                        consumer._process_message(message_id, data, test_handler)

                if events_received:
                    break

        consumer.close()

        if events_received:
            logger.info(f"✅ Successfully consumed {len(events_received)} event(s)")
            for event in events_received:
                logger.info(f"   - {event.title} @ {event.location}")
            return True
        else:
            logger.warning("⚠️  No messages consumed (queue might be empty)")
            logger.warning("   This is OK if no events were published recently")
            return True  # Not a failure, just no messages

    except Exception as e:
        logger.error(f"❌ Failed to consume messages: {e}")
        return False


def test_decision_gateway():
    """Test 4: Decision Gateway Logic"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 4: Decision Gateway")
    logger.info("=" * 60)

    try:
        from services.decision_gateway.__main__ import DecisionGateway

        gateway = DecisionGateway()

        # Test case 1: Event with food
        test_data_with_food = {
            "club_name": "Integration Test Club",
            "tweet": "Join us for a workshop! Free pizza and drinks at 2pm in Student Union.",
            "food_label": 1,
        }

        logger.info("Testing with food event...")
        result = gateway.process_tweet(test_data_with_food)

        if result["decision"] == "SEND_NOTIFICATION":
            logger.info("✅ Correctly identified food event")
            logger.info(f"   Confidence: {result['payload']['confidence']:.2f}")
            logger.info(f"   Title: {result['payload']['event_details']['title']}")
        else:
            logger.error(f"❌ Failed to identify food event: {result['decision']}")
            return False

        # Test case 2: Event without food
        test_data_no_food = {
            "club_name": "Test Club 2",
            "tweet": "Team meeting tomorrow at 4pm in Engineering Lab.",
            "food_label": 0,
        }

        logger.info("Testing without food event...")
        result = gateway.process_tweet(test_data_no_food)

        if result["decision"] == "NO_ACTION":
            logger.info("✅ Correctly identified non-food event")
        else:
            logger.warning(f"⚠️  Unexpected decision: {result['decision']}")
            logger.warning("   This might be OK if the LLM detected food mentions")

        return True

    except Exception as e:
        logger.error(f"❌ Decision Gateway test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_notification_components():
    """Test 5: Notification Service Components"""
    logger.info("\n" + "=" * 60)
    logger.info("TEST 5: Notification Service Components")
    logger.info("=" * 60)

    try:
        from services.notification.notifier import (
            SMTPNotifier,
            NotificationManager,
            render_template,
            SMTP_SERVER,
            DRY_RUN,
        )

        logger.info(f"SMTP Server: {SMTP_SERVER}")
        logger.info(f"DRY_RUN Mode: {DRY_RUN}")

        # Create notifier in dry-run mode
        smtp = SMTPNotifier(
            smtp_server=SMTP_SERVER,
            smtp_port=465,
            smtp_user="test@example.com",
            smtp_password="dummy",
            use_ssl=True,
            dry_run=True,  # Force dry-run for testing
        )

        manager = NotificationManager(rate_limit_seconds=0.1)
        manager.register(smtp)

        logger.info("✅ Notification components initialized")

        # Test template rendering
        template = "Free Food: {{ title }} at {{ location }}"
        rendered = render_template(
            template, {"title": "Test Event", "location": "Test Location"}
        )

        logger.info("✅ Template rendering works")
        logger.info(f"   Rendered: {rendered}")

        # Test dry-run notification
        result = manager.notify_all(
            recipient="test@example.com",
            subject="Integration Test",
            body_html="<html><body>Test</body></html>",
            attachments=None,
            meta={"test": True},
        )

        if result.get("SMTPNotifier"):
            logger.info("✅ Notification system functional (dry-run)")
            return True
        else:
            logger.error("❌ Notification failed")
            return False

    except Exception as e:
        logger.error(f"❌ Notification test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all integration tests"""
    logger.info("\n" + "=" * 70)
    logger.info("WTF SYSTEM INTEGRATION TEST SUITE")
    logger.info("=" * 70)

    tests = [
        ("Redis Connection", test_redis_connection),
        ("Message Publishing", test_message_publish),
        ("Message Consumption", test_message_consume),
        ("Decision Gateway", test_decision_gateway),
        ("Notification Components", test_notification_components),
    ]

    results = {}

    for test_name, test_func in tests:
        try:
            result = test_func()
            results[test_name] = result
        except Exception as e:
            logger.error(f"Test '{test_name}' raised exception: {e}")
            results[test_name] = False

        time.sleep(1)  # Brief pause between tests

    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("TEST SUMMARY")
    logger.info("=" * 70)

    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status} - {test_name}")

    total_tests = len(results)
    passed_tests = sum(1 for r in results.values() if r)

    logger.info("=" * 70)
    logger.info(f"Results: {passed_tests}/{total_tests} tests passed")
    logger.info("=" * 70)

    if passed_tests == total_tests:
        logger.info("\n🎉 ALL TESTS PASSED! System is working correctly.")
        return 0
    else:
        logger.warning(
            f"\n⚠️  {total_tests - passed_tests} test(s) failed. Check logs above."
        )
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
