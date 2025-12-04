import logging
import sys
from datetime import datetime, timezone

from models import FreeFoodEvent
from services.mq import Consumer
from services.config import REDIS_URL, MQ_STREAM

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


class EventProcessor:
    """Processes free food events from the message queue."""

    def __init__(self):
        self.events_processed = 0
        self.events_failed = 0
        self.start_time = datetime.now(timezone.utc)

    def process_event(self, event: FreeFoodEvent) -> None:
        """
        Process a single free food event.

        Args:
            event: The FreeFoodEvent to process
        """
        try:
            logger.info(
                f"Processing event: {event.event_id} | "
                f"Title: {event.title} | "
                f"Location: {event.location} | "
                f"Source: {event.source}"
            )

            # Validate event confidence
            if event.llm_confidence is not None:
                if event.llm_confidence < 0.5:
                    logger.warning(
                        f"Low confidence event ({event.llm_confidence:.2f}): "
                        f"{event.event_id}"
                    )
                else:
                    logger.info(
                        f"High confidence event ({event.llm_confidence:.2f}): "
                        f"{event.event_id}"
                    )

            # Log event details
            if event.reason:
                logger.info(f"Classification reason: {event.reason}")

            if event.start_time:
                logger.info(f"Event starts at: {event.start_time}")

            # Track metrics
            self.events_processed += 1

            # Log processing latency
            if event.published_at:
                latency = (
                    datetime.now(timezone.utc) - event.published_at
                ).total_seconds()
                logger.info(f"Processing latency: {latency:.3f}s")

            # Here you would typically:
            # 1. Store event in database
            # 2. Forward to notification service
            # 3. Update user subscriptions
            # 4. Track analytics

            logger.info(
                f"Successfully processed event {event.event_id}. "
                f"Total processed: {self.events_processed}"
            )

        except Exception as e:
            self.events_failed += 1
            logger.error(
                f"Failed to process event {event.event_id}: {e}", exc_info=True
            )
            raise

    def get_stats(self) -> dict:
        """Get processing statistics."""
        uptime = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        return {
            "events_processed": self.events_processed,
            "events_failed": self.events_failed,
            "uptime_seconds": uptime,
            "events_per_second": (self.events_processed / uptime if uptime > 0 else 0),
        }


def main():
    """Main entry point for the MQ Consumer service."""
    logger.info("Starting MQ Consumer Service...")
    logger.info(f"Redis URL: {REDIS_URL}")
    logger.info(f"Stream: {MQ_STREAM}")

    processor = EventProcessor()

    # Create consumer instance
    consumer = Consumer(
        redis_url=REDIS_URL,
        stream_name=MQ_STREAM,
        consumer_group="mq_consumer_group",
        consumer_name="mq_consumer_worker",
    )

    try:
        logger.info("Consumer ready. Waiting for events...")

        # Start consuming events
        consumer.consume(
            handler=processor.process_event,
            block=5000,
            count=10,  # 5 second timeout
        )

    except KeyboardInterrupt:
        logger.info("Shutting down gracefully...")
        stats = processor.get_stats()
        logger.info(f"Final statistics: {stats}")

    except Exception as e:
        logger.error(f"Fatal error in consumer: {e}", exc_info=True)
        sys.exit(1)

    finally:
        consumer.close()
        logger.info("MQ Consumer Service stopped.")
