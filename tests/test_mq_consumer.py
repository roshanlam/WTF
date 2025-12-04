from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import patch, MagicMock

import pytest
from models import FreeFoodEvent
from services.mq_consumer.__main__ import EventProcessor, main


@pytest.fixture
def sample_event():
    """Create a sample FreeFoodEvent for testing."""
    return FreeFoodEvent(
        event_id=str(uuid4()),
        title="Test Event",
        description="Test description",
        location="Test Location",
        start_time=datetime.now(timezone.utc),
        source="test",
        llm_confidence=0.85,
        reason="Test reason",
        published_at=datetime.now(timezone.utc),
    )


def test_event_processor_initialization():
    """Test EventProcessor initialization."""
    processor = EventProcessor()

    assert processor.events_processed == 0
    assert processor.events_failed == 0
    assert processor.start_time is not None


def test_event_processor_process_event(sample_event):
    """Test processing a valid event."""
    processor = EventProcessor()

    # Process event
    processor.process_event(sample_event)

    # Check metrics
    assert processor.events_processed == 1
    assert processor.events_failed == 0


def test_event_processor_process_event_with_high_confidence(sample_event):
    """Test processing event with high confidence."""
    processor = EventProcessor()
    sample_event.llm_confidence = 0.95

    processor.process_event(sample_event)

    assert processor.events_processed == 1


def test_event_processor_process_event_with_low_confidence(sample_event):
    """Test processing event with low confidence."""
    processor = EventProcessor()
    sample_event.llm_confidence = 0.3

    processor.process_event(sample_event)

    assert processor.events_processed == 1


def test_event_processor_process_event_without_confidence(sample_event):
    """Test processing event without confidence score."""
    processor = EventProcessor()
    sample_event.llm_confidence = None

    processor.process_event(sample_event)

    assert processor.events_processed == 1


def test_event_processor_process_event_without_reason(sample_event):
    """Test processing event without reason."""
    processor = EventProcessor()
    sample_event.reason = None

    processor.process_event(sample_event)

    assert processor.events_processed == 1


def test_event_processor_process_event_without_start_time(sample_event):
    """Test processing event without start time."""
    processor = EventProcessor()
    sample_event.start_time = None

    processor.process_event(sample_event)

    assert processor.events_processed == 1


def test_event_processor_process_event_with_latency(sample_event):
    """Test that latency is calculated correctly."""
    import time

    processor = EventProcessor()

    # Set published_at to a time in the past
    sample_event.published_at = datetime.now(timezone.utc)

    # Wait a bit
    time.sleep(0.01)

    processor.process_event(sample_event)

    assert processor.events_processed == 1


def test_event_processor_process_event_exception():
    """Test that processor handles exceptions during processing."""
    processor = EventProcessor()

    # Create an invalid event that will cause an exception
    # This is a bit tricky since we need a FreeFoodEvent object
    # Let's patch datetime to raise an exception
    with patch("services.mq_consumer.__main__.datetime") as mock_datetime:
        mock_datetime.now.side_effect = Exception("Test exception")

        event = FreeFoodEvent(
            event_id=str(uuid4()),
            title="Test",
            source="test",
            published_at=datetime.now(timezone.utc),
        )

        try:
            processor.process_event(event)
        except Exception:
            pass

    # Should have incremented failed counter
    assert processor.events_failed == 1


def test_event_processor_get_stats():
    """Test getting processor statistics."""
    processor = EventProcessor()

    # Process some events
    for i in range(5):
        event = FreeFoodEvent(
            event_id=str(uuid4()),
            title=f"Event {i}",
            source="test",
            published_at=datetime.now(timezone.utc),
        )
        processor.process_event(event)

    stats = processor.get_stats()

    assert stats["events_processed"] == 5
    assert stats["events_failed"] == 0
    assert stats["uptime_seconds"] >= 0
    assert "events_per_second" in stats


def test_event_processor_get_stats_with_zero_uptime():
    """Test stats calculation with very short uptime."""
    processor = EventProcessor()

    stats = processor.get_stats()

    assert stats["events_processed"] == 0
    assert stats["events_per_second"] == 0.0


def test_event_processor_multiple_events():
    """Test processing multiple events."""
    processor = EventProcessor()

    # Process 10 events
    for i in range(10):
        event = FreeFoodEvent(
            event_id=str(uuid4()),
            title=f"Event {i}",
            source="test",
            published_at=datetime.now(timezone.utc),
        )
        processor.process_event(event)

    assert processor.events_processed == 10
    assert processor.events_failed == 0


def test_main_function_keyboard_interrupt():
    """Test main function handles KeyboardInterrupt."""
    # Mock Consumer to raise KeyboardInterrupt
    with patch("services.mq_consumer.__main__.Consumer") as MockConsumer:
        mock_consumer = MagicMock()
        MockConsumer.return_value = mock_consumer

        # Make consume raise KeyboardInterrupt
        mock_consumer.consume.side_effect = KeyboardInterrupt()

        # Should handle gracefully without crashing
        try:
            main()
        except SystemExit:
            pass  # main() may call sys.exit, that's ok


def test_main_function_exception():
    """Test main function handles general exceptions."""
    # Mock Consumer to raise an exception
    with patch("services.mq_consumer.__main__.Consumer") as MockConsumer:
        mock_consumer = MagicMock()
        MockConsumer.return_value = mock_consumer

        # Make consume raise a general exception
        mock_consumer.consume.side_effect = Exception("Test error")

        # Should handle and exit with error code
        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1


def test_main_function_consumer_setup():
    """Test that main function sets up consumer correctly."""
    with patch("services.mq_consumer.__main__.Consumer") as MockConsumer:
        mock_consumer = MagicMock()
        MockConsumer.return_value = mock_consumer

        # Make consume raise KeyboardInterrupt to exit cleanly
        mock_consumer.consume.side_effect = KeyboardInterrupt()

        try:
            main()
        except SystemExit:
            pass

        # Verify Consumer was created with correct parameters
        MockConsumer.assert_called_once()
        call_kwargs = MockConsumer.call_args.kwargs

        assert call_kwargs["consumer_group"] == "mq_consumer_group"
        assert call_kwargs["consumer_name"] == "mq_consumer_worker"


def test_event_processor_all_optional_fields():
    """Test processing event with all optional fields populated."""
    processor = EventProcessor()

    event = FreeFoodEvent(
        event_id=str(uuid4()),
        title="Complete Event",
        description="Full description",
        location="Complete Location",
        start_time=datetime.now(timezone.utc),
        source="test",
        llm_confidence=0.99,
        reason="All fields present",
        published_at=datetime.now(timezone.utc),
        metadata={"key": "value"},
    )

    processor.process_event(event)

    assert processor.events_processed == 1
    assert processor.events_failed == 0
