"""Notification service entrypoint.

This consumer listens to the message queue for `FreeFoodEvent` messages
and forwards notifications (email) using the `services.notification.notifier`
helper classes.

Behavior:
- Reads recipients from `NOTIFICATION_RECIPIENTS` env var (comma-separated).
- Uses SMTP config from the notifier module (env-driven).
"""

import logging
import sys
from datetime import timezone, datetime
from typing import List

from models import FreeFoodEvent
from services.mq import Consumer
from services.config import REDIS_URL, MQ_STREAM
from services.notification.notifier import (
    SMTPNotifier,
    NotificationManager,
    render_template,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


def _get_recipients() -> List[str]:
    raw = __import__("os").environ.get("NOTIFICATION_RECIPIENTS", "")
    if not raw:
        return []
    return [r.strip() for r in raw.split(",") if r.strip()]


class NotificationProcessor:
    def __init__(self, manager: NotificationManager):
        self.manager = manager
        self.events_processed = 0
        self.events_failed = 0
        self.start_time = datetime.now(timezone.utc)

    def process_event(self, event: FreeFoodEvent) -> None:
        try:
            logger.info(
                f"Processing event {event.event_id} — {event.title} @ {event.location}"
            )

            subject_tpl = "Free Food: {{ title }} — {{ location or 'TBD' }}"
            body_tpl = (
                "<html><body>"
                "<h3>{{ title }}</h3>"
                "<p><strong>When:</strong> {{ start_time or 'TBD' }}</p>"
                "<p><strong>Where:</strong> {{ location or 'TBD' }}</p>"
                "<p>{{ description or '' }}</p>"
                "<p>Confidence: {{ llm_confidence }}</p>"
                "</body></html>"
            )

            context = {
                "title": event.title,
                "location": event.location,
                "start_time": event.start_time.isoformat() if event.start_time else None,
                "description": event.description,
                "llm_confidence": event.llm_confidence,
            }

            subject = render_template(subject_tpl, context)
            body = render_template(body_tpl, context)

            recipients = _get_recipients()
            if not recipients:
                logger.warning("No recipients configured (NOTIFICATION_RECIPIENTS). Skipping send.")
                return

            for r in recipients:
                ok_map = self.manager.notify_all(r, subject, body, attachments=None, meta=event.model_dump())
                logger.info(f"Send result for {r}: {ok_map}")

            self.events_processed += 1

        except Exception as e:
            self.events_failed += 1
            logger.error(f"Failed to process/notify for event {event.event_id}: {e}", exc_info=True)
            raise


def main():
    logger.info("Starting Notification Service")
    logger.info(f"Redis URL: {REDIS_URL}")
    logger.info(f"Stream: {MQ_STREAM}")

    # Create notifier and manager (notifier reads SMTP config from env)
    smtp = SMTPNotifier(
        smtp_server=SMTPNotifier.__init__.__defaults__ and SMTPNotifier.__init__.__defaults__[0],
        smtp_port=SMTPNotifier.__init__.__defaults__ and SMTPNotifier.__init__.__defaults__[1],
        smtp_user=None,
        smtp_password=None,
    )

    # Instead of trying to introspect defaults above (which is brittle), import the module-level
    # constants by re-importing the module and using them if available. Fall back to simple ctor usage.
    try:
        from services.notification import notifier as _notifier_mod

        smtp = SMTPNotifier(
            smtp_server=_notifier_mod.SMTP_SERVER,
            smtp_port=_notifier_mod.SMTP_PORT,
            smtp_user=_notifier_mod.SMTP_USER,
            smtp_password=_notifier_mod.SMTP_PASSWORD,
            use_ssl=getattr(_notifier_mod, "USE_SSL", True),
            use_starttls=getattr(_notifier_mod, "USE_STARTTLS", False),
            dry_run=getattr(_notifier_mod, "DRY_RUN", False),
        )
    except Exception:
        logger.exception("Failed to create SMTPNotifier from notifier module; trying basic constructor")

    manager = NotificationManager(rate_limit_seconds=1.0)
    manager.register(smtp)

    processor = NotificationProcessor(manager=manager)

    consumer = Consumer(
        redis_url=REDIS_URL,
        stream_name=MQ_STREAM,
        consumer_group="notification_service_group",
        consumer_name="notification_worker",
    )

    try:
        logger.info("Notification service ready — waiting for events...")
        consumer.consume(handler=processor.process_event, block=5000, count=10)

    except KeyboardInterrupt:
        logger.info("Shutting down notification service (keyboard interrupt)")
        stats = processor.__dict__
        logger.info(f"Final stats: {stats}")

    except Exception as e:
        logger.error(f"Fatal error in notification service: {e}", exc_info=True)
        sys.exit(1)

    finally:
        consumer.close()
        logger.info("Notification service stopped")


if __name__ == "__main__":
    main()
