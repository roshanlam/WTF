import json
from datetime import datetime, timezone
from uuid import uuid4
import pytest
from models import FreeFoodEvent
from services.mq import MessageQueue, Consumer


@pytest.fixture
def sample_event():
    return FreeFoodEvent(
        event_id=str(uuid4()),
        title="Free Pizza Night",
        description="Join us for free pizza",
        location="CS Building",
        start_time=datetime.now(timezone.utc),
        source="test",
        published_at=datetime.now(timezone.utc),
    )


def test_message_queue_publish(sample_event):
    mq = MessageQueue()
    message_id = mq.publish(sample_event)
    assert message_id is not None
    mq.close()


def test_consumer_process_message(sample_event):
    events_received = []

    def handler(event: FreeFoodEvent):
        events_received.append(event)

    mq = MessageQueue()
    consumer = Consumer(consumer_group="test_group", consumer_name="test_worker")

    mq.publish(sample_event)

    message_data = {"data": json.dumps(sample_event.model_dump(mode="json"))}
    consumer._process_message("test-msg-id", message_data, handler)

    assert len(events_received) == 1
    assert events_received[0].event_id == sample_event.event_id

    mq.close()
    consumer.close()
