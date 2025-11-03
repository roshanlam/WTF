import json
import logging
from typing import Any, Callable, Optional
from redis import Redis
from models import FreeFoodEvent
from services.config import REDIS_URL, MQ_STREAM

logger = logging.getLogger(__name__)


class MessageQueue:
    def __init__(self, redis_url: str = REDIS_URL, stream_name: str = MQ_STREAM):
        self.redis_url = redis_url
        self.stream_name = stream_name
        self._client: Optional[Redis] = None

    @property
    def client(self) -> Redis:
        if self._client is None:
            self._client = Redis.from_url(self.redis_url, decode_responses=True)
        return self._client

    def publish(self, event: FreeFoodEvent) -> str:
        event_data = event.model_dump(mode="json")
        event_json = json.dumps(event_data)
        message_id = str(self.client.xadd(self.stream_name, {"data": event_json}))
        logger.info(f"Published event {event.event_id} to {self.stream_name}")
        return message_id

    def close(self):
        if self._client:
            self._client.close()
            self._client = None


class Consumer:
    def __init__(
        self,
        redis_url: str = REDIS_URL,
        stream_name: str = MQ_STREAM,
        consumer_group: str = "default",
        consumer_name: str = "worker",
    ):
        self.redis_url = redis_url
        self.stream_name = stream_name
        self.consumer_group = consumer_group
        self.consumer_name = consumer_name
        self._client: Optional[Redis] = None

    @property
    def client(self) -> Redis:
        if self._client is None:
            self._client = Redis.from_url(self.redis_url, decode_responses=True)
            self._ensure_consumer_group()
        return self._client

    def _ensure_consumer_group(self):
        try:
            self._client.xgroup_create(
                self.stream_name, self.consumer_group, id="0", mkstream=True
            )
            logger.info(f"Created consumer group {self.consumer_group}")
        except Exception as e:
            if "BUSYGROUP" not in str(e):
                logger.error(f"Error creating consumer group: {e}")

    def consume(
        self,
        handler: Callable[[FreeFoodEvent], None],
        block: int = 5000,
        count: int = 10,
    ):
        logger.info(f"Starting consumer {self.consumer_name} on {self.stream_name}")

        while True:
            try:
                messages = self.client.xreadgroup(
                    self.consumer_group,
                    self.consumer_name,
                    {self.stream_name: ">"},
                    count=count,
                    block=block,
                )

                if not messages:
                    continue

                for stream, message_list in messages:  # type: ignore[union-attr]
                    for message_id, data in message_list:
                        self._process_message(message_id, data, handler)

            except KeyboardInterrupt:
                logger.info("Consumer shutting down")
                break
            except Exception as e:
                logger.error(f"Error in consumer loop: {e}")

    def _process_message(
        self,
        message_id: str,
        data: dict[str, Any],
        handler: Callable[[FreeFoodEvent], None],
    ):
        try:
            event_data = json.loads(data.get("data", "{}"))
            event = FreeFoodEvent(**event_data)

            major_version = event.schema_version.split(".")[0]
            if major_version != "1":
                logger.warning(f"Unsupported schema version: {event.schema_version}")

            handler(event)
            self.client.xack(self.stream_name, self.consumer_group, message_id)
            logger.info(f"Processed event {event.event_id}")

        except Exception as e:
            logger.error(f"Error processing message {message_id}: {e}")

    def close(self):
        if self._client:
            self._client.close()
            self._client = None
