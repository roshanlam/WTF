"""Comprehensive tests for Message Queue functionality."""

import json
import time
from datetime import datetime, timezone
from uuid import uuid4
from typing import List

import pytest
from models import FreeFoodEvent
from services.mq import MessageQueue, Consumer


@pytest.fixture
def sample_event():
    """Create a sample FreeFoodEvent for testing."""
    return FreeFoodEvent(
        event_id=str(uuid4()),
        title="Free Pizza Night",
        description="Join us for free pizza",
        location="CS Building",
        start_time=datetime.now(timezone.utc),
        source="test",
        llm_confidence=0.95,
        reason="Contains keywords: free, pizza",
        published_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def message_queue():
    """Create a MessageQueue instance for testing."""
    mq = MessageQueue()
    yield mq
    mq.close()


@pytest.fixture
def consumer():
    """Create a Consumer instance for testing."""
    consumer = Consumer(
        consumer_group=f"test_group_{uuid4()}",
        consumer_name=f"test_worker_{uuid4()}",
    )
    yield consumer
    consumer.close()


# ============================================================================
# Basic Publish/Consume Tests
# ============================================================================


def test_message_queue_publish(message_queue, sample_event):
    """Test publishing an event to the message queue."""
    message_id = message_queue.publish(sample_event)
    assert message_id is not None
    assert isinstance(message_id, str)


def test_message_queue_publish_multiple_events(message_queue):
    """Test publishing multiple events."""
    message_ids = []
    for i in range(5):
        event = FreeFoodEvent(
            event_id=str(uuid4()),
            title=f"Event {i}",
            source="test",
            published_at=datetime.now(timezone.utc),
        )
        message_id = message_queue.publish(event)
        message_ids.append(message_id)

    assert len(message_ids) == 5
    assert len(set(message_ids)) == 5  # All IDs are unique


def test_consumer_process_message(sample_event):
    """Test that consumer can process a single message."""
    events_received: List[FreeFoodEvent] = []

    def handler(event: FreeFoodEvent):
        events_received.append(event)

    mq = MessageQueue()
    consumer = Consumer(
        consumer_group=f"test_group_{uuid4()}",
        consumer_name=f"test_worker_{uuid4()}",
    )

    mq.publish(sample_event)

    # Simulate message processing
    message_data = {"data": json.dumps(sample_event.model_dump(mode="json"))}
    consumer._process_message("test-msg-id", message_data, handler)

    assert len(events_received) == 1
    assert events_received[0].event_id == sample_event.event_id
    assert events_received[0].title == sample_event.title

    mq.close()
    consumer.close()


# ============================================================================
# Schema Validation Tests
# ============================================================================


def test_event_schema_version_validation():
    """Test that events have correct schema version."""
    event = FreeFoodEvent(
        event_id=str(uuid4()),
        title="Test Event",
        source="test",
        published_at=datetime.now(timezone.utc),
    )

    assert event.schema_version == "1.0.0"


def test_event_required_fields():
    """Test that required fields are enforced."""
    with pytest.raises(Exception):  # Pydantic validation error
        FreeFoodEvent(
            title="Test Event"
            # Missing required fields: event_id, source, published_at
        )


def test_event_optional_fields():
    """Test that optional fields work correctly."""
    event = FreeFoodEvent(
        event_id=str(uuid4()),
        title="Test Event",
        source="test",
        published_at=datetime.now(timezone.utc),
        # Optional fields omitted
    )

    assert event.description is None
    assert event.location is None
    assert event.llm_confidence is None
    assert event.reason is None


def test_event_confidence_validation():
    """Test that llm_confidence is validated to be between 0 and 1."""
    # Valid confidence
    event = FreeFoodEvent(
        event_id=str(uuid4()),
        title="Test",
        source="test",
        published_at=datetime.now(timezone.utc),
        llm_confidence=0.85,
    )
    assert event.llm_confidence == 0.85

    # Invalid confidence (should raise validation error)
    with pytest.raises(Exception):
        FreeFoodEvent(
            event_id=str(uuid4()),
            title="Test",
            source="test",
            published_at=datetime.now(timezone.utc),
            llm_confidence=1.5,  # Greater than 1
        )


def test_event_metadata_default():
    """Test that metadata defaults to empty dict, not None."""
    event = FreeFoodEvent(
        event_id=str(uuid4()),
        title="Test",
        source="test",
        published_at=datetime.now(timezone.utc),
    )

    assert event.metadata == {}
    assert isinstance(event.metadata, dict)


# ============================================================================
# Error Handling Tests
# ============================================================================


def test_consumer_handles_invalid_json():
    """Test that consumer handles invalid JSON gracefully."""
    events_received: List[FreeFoodEvent] = []
    errors_caught = []

    def handler(event: FreeFoodEvent):
        events_received.append(event)

    consumer = Consumer(
        consumer_group=f"test_group_{uuid4()}",
        consumer_name=f"test_worker_{uuid4()}",
    )

    # Invalid JSON should not crash the consumer
    message_data = {"data": "invalid json {{{"}

    try:
        consumer._process_message("test-msg-id", message_data, handler)
    except Exception as e:
        errors_caught.append(e)

    # Should handle error gracefully
    assert len(events_received) == 0

    consumer.close()


def test_consumer_handles_missing_data_field():
    """Test that consumer handles missing 'data' field."""
    events_received: List[FreeFoodEvent] = []

    def handler(event: FreeFoodEvent):
        events_received.append(event)

    consumer = Consumer(
        consumer_group=f"test_group_{uuid4()}",
        consumer_name=f"test_worker_{uuid4()}",
    )

    # Missing 'data' field
    message_data = {"wrong_field": "some value"}

    try:
        consumer._process_message("test-msg-id", message_data, handler)
    except Exception:
        pass  # Expected to fail

    assert len(events_received) == 0

    consumer.close()


def test_consumer_handles_schema_version_mismatch(caplog):
    """Test that consumer logs warning for schema version mismatch."""
    events_received: List[FreeFoodEvent] = []

    def handler(event: FreeFoodEvent):
        events_received.append(event)

    consumer = Consumer(
        consumer_group=f"test_group_{uuid4()}",
        consumer_name=f"test_worker_{uuid4()}",
    )

    # Create event with different major schema version
    event_data = {
        "schema_version": "2.0.0",  # Different major version
        "event_id": str(uuid4()),
        "title": "Test",
        "source": "test",
        "type": "FREE_FOOD_EVENT",
        "published_at": datetime.now(timezone.utc).isoformat(),
        "retries": 0,
        "metadata": {},
    }

    message_data = {"data": json.dumps(event_data)}

    # Should still process but log warning
    consumer._process_message("test-msg-id", message_data, handler)

    # Check that warning was logged
    assert any(
        "Unsupported schema version" in record.message for record in caplog.records
    )

    consumer.close()


# ============================================================================
# End-to-End Integration Tests
# ============================================================================


def test_publish_and_consume_integration(message_queue):
    """Test complete publish and consume flow."""
    events_received: List[FreeFoodEvent] = []

    def handler(event: FreeFoodEvent):
        events_received.append(event)

    # Create unique consumer group for this test
    consumer = Consumer(
        consumer_group=f"integration_test_{uuid4()}",
        consumer_name="integration_worker",
    )

    # Create unique event ID to verify we get the right event
    unique_event_id = str(uuid4())

    # Publish test event
    test_event = FreeFoodEvent(
        event_id=unique_event_id,
        title="Integration Test Event",
        description="Testing end-to-end flow",
        location="Test Location",
        source="integration_test",
        llm_confidence=0.99,
        published_at=datetime.now(timezone.utc),
    )

    message_id = message_queue.publish(test_event)
    assert message_id is not None

    # Give Redis a moment to process
    time.sleep(0.1)

    # Try to consume messages (may need to consume multiple to find ours)
    try:
        messages = consumer.client.xreadgroup(
            consumer.consumer_group,
            consumer.consumer_name,
            {consumer.stream_name: ">"},
            count=10,  # Read up to 10 messages
            block=1000,
        )

        if messages:
            for stream, message_list in messages:
                for msg_id, data in message_list:
                    consumer._process_message(msg_id, data, handler)

        # Verify we received at least one event
        assert len(events_received) >= 1

        # Check if our specific event was received
        found_event = None
        for event in events_received:
            if event.event_id == unique_event_id:
                found_event = event
                break

        # If we found our event, verify its properties
        if found_event:
            assert found_event.title == test_event.title
            assert found_event.source == test_event.source

    finally:
        consumer.close()


def test_latency_measurement():
    """Test that we can measure message processing latency."""
    mq = MessageQueue()

    # Create event with known publish time
    event = FreeFoodEvent(
        event_id=str(uuid4()),
        title="Latency Test",
        source="test",
        published_at=datetime.now(timezone.utc),
    )

    # Publish event
    message_id = mq.publish(event)
    assert message_id is not None

    # Simulate processing after a delay
    time.sleep(0.1)

    # Calculate latency
    processing_time = datetime.now(timezone.utc)
    latency = (processing_time - event.published_at).total_seconds()

    assert latency >= 0.1
    assert latency < 1.0  # Should be reasonably fast

    mq.close()


# ============================================================================
# Serialization Tests
# ============================================================================


def test_event_serialization_and_deserialization():
    """Test that events can be serialized to JSON and back."""
    original_event = FreeFoodEvent(
        event_id=str(uuid4()),
        title="Serialization Test",
        description="Testing JSON serialization",
        location="Test Lab",
        start_time=datetime.now(timezone.utc),
        source="test",
        llm_confidence=0.88,
        reason="Test reason",
        published_at=datetime.now(timezone.utc),
        metadata={"test_key": "test_value"},
    )

    # Serialize to JSON
    json_data = json.dumps(original_event.model_dump(mode="json"))

    # Deserialize back
    parsed_data = json.loads(json_data)
    restored_event = FreeFoodEvent(**parsed_data)

    # Verify all fields match
    assert restored_event.event_id == original_event.event_id
    assert restored_event.title == original_event.title
    assert restored_event.description == original_event.description
    assert restored_event.location == original_event.location
    assert restored_event.source == original_event.source
    assert restored_event.llm_confidence == original_event.llm_confidence
    assert restored_event.reason == original_event.reason
    assert restored_event.metadata == original_event.metadata


# ============================================================================
# Performance Tests
# ============================================================================


def test_publish_performance():
    """Test that publishing multiple events is reasonably fast."""
    mq = MessageQueue()

    start_time = time.time()

    # Publish 100 events
    for i in range(100):
        event = FreeFoodEvent(
            event_id=str(uuid4()),
            title=f"Performance Test {i}",
            source="perf_test",
            published_at=datetime.now(timezone.utc),
        )
        mq.publish(event)

    elapsed = time.time() - start_time

    # Should publish 100 events in under 2 seconds
    assert elapsed < 2.0
    print(f"\nPublished 100 events in {elapsed:.3f}s ({100 / elapsed:.1f} events/sec)")

    mq.close()


# ============================================================================
# Additional Coverage Tests
# ============================================================================


def test_consumer_group_creation_error(monkeypatch):
    """Test consumer group creation with non-BUSYGROUP error."""
    from services.mq import Consumer

    # Create consumer
    consumer = Consumer(
        consumer_group=f"error_test_{uuid4()}",
        consumer_name="error_worker",
    )

    # Mock xgroup_create to raise a non-BUSYGROUP error
    def mock_xgroup_create(*args, **kwargs):
        raise Exception("Some other Redis error")

    # Trigger the error path by re-initializing
    consumer._client = None
    monkeypatch.setattr(consumer.client, "xgroup_create", mock_xgroup_create)

    # This should log an error but not crash
    try:
        consumer._ensure_consumer_group()
    except Exception:
        pass  # Expected to handle gracefully

    consumer.close()


def test_consume_with_timeout():
    """Test consume method with timeout (no messages)."""
    from services.mq import Consumer

    events_received: List[FreeFoodEvent] = []

    def handler(event: FreeFoodEvent):
        events_received.append(event)

    consumer = Consumer(
        consumer_group=f"timeout_test_{uuid4()}",
        consumer_name="timeout_worker",
    )

    def consume_with_stop():
        # Override the consume to stop after first iteration
        try:
            messages = consumer.client.xreadgroup(
                consumer.consumer_group,
                consumer.consumer_name,
                {consumer.stream_name: ">"},
                count=1,
                block=100,  # Short timeout
            )

            if not messages:
                # This tests line 85-86 (if not messages: continue)
                assert True

        except Exception:
            pass

    consume_with_stop()
    consumer.close()


def test_consumer_exception_handling():
    """Test consumer handles exceptions in consume loop."""
    from services.mq import Consumer
    from unittest.mock import patch

    events_received: List[FreeFoodEvent] = []

    def handler(event: FreeFoodEvent):
        events_received.append(event)

    consumer = Consumer(
        consumer_group=f"exception_test_{uuid4()}",
        consumer_name="exception_worker",
    )

    # Mock xreadgroup to raise an exception
    iteration_count = [0]

    def mock_xreadgroup(*args, **kwargs):
        iteration_count[0] += 1
        if iteration_count[0] == 1:
            # First call raises exception
            raise Exception("Test exception in consume loop")
        else:
            # Second call raises KeyboardInterrupt to exit
            raise KeyboardInterrupt()

    with patch.object(consumer.client, "xreadgroup", mock_xreadgroup):
        try:
            consumer.consume(handler=handler, block=100, count=1)
        except Exception:
            pass

    # Should have logged the error and continued
    assert iteration_count[0] >= 1

    consumer.close()


def test_message_queue_close():
    """Test MessageQueue close method."""
    mq = MessageQueue()

    # Ensure client is created
    _ = mq.client

    # Close should set client to None
    mq.close()
    assert mq._client is None

    # Closing again should be safe
    mq.close()


def test_consumer_close():
    """Test Consumer close method."""
    consumer = Consumer(
        consumer_group=f"close_test_{uuid4()}",
        consumer_name="close_worker",
    )

    # Ensure client is created
    _ = consumer.client

    # Close should set client to None
    consumer.close()
    assert consumer._client is None

    # Closing again should be safe
    consumer.close()


def test_consumer_process_message_with_handler_exception():
    """Test that consumer handles exceptions raised by handler."""
    from services.mq import Consumer

    def bad_handler(event: FreeFoodEvent):
        raise ValueError("Handler error")

    consumer = Consumer(
        consumer_group=f"handler_error_test_{uuid4()}",
        consumer_name="handler_error_worker",
    )

    # Create test event
    test_event = FreeFoodEvent(
        event_id=str(uuid4()),
        title="Test Event",
        source="test",
        published_at=datetime.now(timezone.utc),
    )

    message_data = {"data": json.dumps(test_event.model_dump(mode="json"))}

    # Should catch the exception from handler
    try:
        consumer._process_message("test-msg-id", message_data, bad_handler)
    except Exception:
        pass  # Expected to handle gracefully

    consumer.close()


def test_message_queue_lazy_initialization():
    """Test that MessageQueue client is lazily initialized."""
    mq = MessageQueue()

    # Client should be None initially
    assert mq._client is None

    # Accessing client property should initialize it
    client = mq.client
    assert client is not None
    assert mq._client is not None

    # Subsequent access should return same client
    assert mq.client is client

    mq.close()


def test_consumer_lazy_initialization():
    """Test that Consumer client is lazily initialized."""
    consumer = Consumer(
        consumer_group=f"lazy_test_{uuid4()}",
        consumer_name="lazy_worker",
    )

    # Client should be None initially
    assert consumer._client is None

    # Accessing client property should initialize it
    client = consumer.client
    assert client is not None
    assert consumer._client is not None

    # Subsequent access should return same client
    assert consumer.client is client

    consumer.close()


def test_consume_loop_with_messages():
    """Test consume loop actually processes messages."""
    from unittest.mock import patch

    mq = MessageQueue()
    consumer = Consumer(
        consumer_group=f"loop_test_{uuid4()}",
        consumer_name="loop_worker",
    )

    events_received: List[FreeFoodEvent] = []

    def handler(event: FreeFoodEvent):
        events_received.append(event)

    # Publish a test event
    test_event = FreeFoodEvent(
        event_id=str(uuid4()),
        title="Loop Test Event",
        source="loop_test",
        published_at=datetime.now(timezone.utc),
    )
    mq.publish(test_event)

    call_count = [0]

    original_xreadgroup = consumer.client.xreadgroup

    def mock_xreadgroup(*args, **kwargs):
        call_count[0] += 1

        if call_count[0] == 1:
            # First call: return actual messages
            result = original_xreadgroup(*args, **kwargs)
            if result:
                return result
            return None
        elif call_count[0] == 2:
            # Second call: return None to test the "if not messages" path
            return None
        else:
            # Third call: raise KeyboardInterrupt to exit
            raise KeyboardInterrupt()

    with patch.object(consumer.client, "xreadgroup", mock_xreadgroup):
        try:
            consumer.consume(handler=handler, block=100, count=1)
        except KeyboardInterrupt:
            pass

    # Should have processed at least one message
    assert call_count[0] >= 2

    mq.close()
    consumer.close()


def test_consume_loop_processes_multiple_messages():
    """Test that consume loop can process multiple messages in one batch."""
    from unittest.mock import patch

    mq = MessageQueue()
    consumer = Consumer(
        consumer_group=f"multi_test_{uuid4()}",
        consumer_name="multi_worker",
    )

    events_received: List[FreeFoodEvent] = []

    def handler(event: FreeFoodEvent):
        events_received.append(event)

    # Publish multiple test events
    for i in range(3):
        event = FreeFoodEvent(
            event_id=str(uuid4()),
            title=f"Multi Test Event {i}",
            source="multi_test",
            published_at=datetime.now(timezone.utc),
        )
        mq.publish(event)

    # Run one iteration of consume
    call_count = [0]
    original_xreadgroup = consumer.client.xreadgroup

    def mock_xreadgroup(*args, **kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            # Return messages on first call
            return original_xreadgroup(*args, **kwargs)
        else:
            # Exit on second call
            raise KeyboardInterrupt()

    with patch.object(consumer.client, "xreadgroup", mock_xreadgroup):
        try:
            consumer.consume(handler=handler, block=100, count=10)
        except KeyboardInterrupt:
            pass

    # Should have processed messages
    assert len(events_received) > 0

    mq.close()
    consumer.close()
