import logging
import sys
from datetime import datetime, timezone

from models import FreeFoodEvent
from services.mq import Consumer
from services.config import REDIS_URL, MQ_STREAM
from services.notifications.__main__ import NotificationService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


class EventProcessor:
    """Processes free food events from the message queue and sends notifications."""

    def __init__(self, notification_service: NotificationService = None):
        self.events_processed = 0
        self.events_failed = 0
        self.notifications_sent = 0
        self.notifications_failed = 0
        self.start_time = datetime.now(timezone.utc)
        
        # Initialize notification service
        try:
            self.notification_service = notification_service or NotificationService()
            logger.info("[PROCESSOR] Notification service initialized")
        except Exception as e:
            logger.error(f"[PROCESSOR] Failed to initialize notification service: {e}")
            self.notification_service = None

    def process_event(self, event: FreeFoodEvent) -> None:
        """
        Process a single free food event and send notification if applicable.

        Args:
            event: The FreeFoodEvent to process
        """
        try:
            logger.info(
                f"[PROCESSOR] Processing event: {event.event_id} | "
                f"Title: {event.title} | "
                f"Location: {event.location} | "
                f"Source: {event.source}"
            )

            # Validate event confidence
            if event.llm_confidence is not None:
                if event.llm_confidence < 0.5:
                    logger.warning(
                        f"[PROCESSOR] Low confidence event ({event.llm_confidence:.2f}): "
                        f"{event.event_id}"
                    )
                else:
                    logger.info(
                        f"[PROCESSOR] High confidence event ({event.llm_confidence:.2f}): "
                        f"{event.event_id}"
                    )

            # Log event details
            if event.reason:
                logger.info(f"[PROCESSOR] Classification reason: {event.reason}")

            if event.start_time:
                logger.info(f"[PROCESSOR] Event starts at: {event.start_time}")

            # Send notification via Twilio
            if self.notification_service:
                try:
                    notification_sent = self.notification_service.send_notification(event)
                    if notification_sent:
                        self.notifications_sent += 1
                        logger.info(
                            f"[PROCESSOR] ✓ Notification sent for event {event.event_id}"
                        )
                    else:
                        self.notifications_failed += 1
                        logger.warning(
                            f"[PROCESSOR] ✗ Notification failed for event {event.event_id}"
                        )
                except Exception as e:
                    self.notifications_failed += 1
                    logger.error(
                        f"[PROCESSOR] Error sending notification for {event.event_id}: {e}",
                        exc_info=True
                    )
            else:
                logger.warning(
                    "[PROCESSOR] Notification service not available, skipping notification"
                )

            # Track metrics
            self.events_processed += 1

            # Log processing latency
            if event.published_at:
                now = datetime.now(timezone.utc)
                pub_time = event.published_at
                if pub_time.tzinfo is None:
                    pub_time = pub_time.replace(tzinfo=timezone.utc)
                latency = (now - pub_time).total_seconds()
                logger.info(f"[PROCESSOR] Processing latency: {latency:.3f}s")

            # Here you would typically also:
            # 1. Store event in database
            # 2. Update user subscriptions
            # 3. Track analytics

            logger.info(
                f"[PROCESSOR] Successfully processed event {event.event_id}. "
                f"Total processed: {self.events_processed}, "
                f"Notifications sent: {self.notifications_sent}"
            )

        except Exception as e:
            self.events_failed += 1
            logger.error(
                f"[PROCESSOR] Failed to process event {event.event_id}: {e}", 
                exc_info=True
            )
            raise

    def get_stats(self) -> dict:
        """Get processing statistics."""
        uptime = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        return {
            "events_processed": self.events_processed,
            "events_failed": self.events_failed,
            "notifications_sent": self.notifications_sent,
            "notifications_failed": self.notifications_failed,
            "uptime_seconds": uptime,
            "events_per_second": (self.events_processed / uptime if uptime > 0 else 0),
        }


def main():
    """Main entry point for the MQ Consumer service."""
    logger.info("=" * 80)
    logger.info("Starting MQ Consumer Service with Notifications")
    logger.info("=" * 80)
    logger.info(f"Redis URL: {REDIS_URL}")
    logger.info(f"Stream: {MQ_STREAM}")

    # Initialize processor with notification service
    try:
        processor = EventProcessor()
    except Exception as e:
        logger.error(f"Failed to initialize processor: {e}")
        sys.exit(1)

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
            block=5000,  # 5 second timeout
            count=10,
        )

    except KeyboardInterrupt:
        logger.info("\n" + "=" * 80)
        logger.info("Shutting down gracefully...")
        stats = processor.get_stats()
        logger.info("Final statistics:")
        logger.info(f"  Events processed: {stats['events_processed']}")
        logger.info(f"  Events failed: {stats['events_failed']}")
        logger.info(f"  Notifications sent: {stats['notifications_sent']}")
        logger.info(f"  Notifications failed: {stats['notifications_failed']}")
        logger.info(f"  Uptime: {stats['uptime_seconds']:.2f}s")
        logger.info(f"  Events/second: {stats['events_per_second']:.2f}")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"Fatal error in consumer: {e}", exc_info=True)
        sys.exit(1)

    finally:
        consumer.close()
        logger.info("MQ Consumer Service stopped.")


if __name__ == "__main__":
    main()