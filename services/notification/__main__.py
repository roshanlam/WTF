import asyncio
import logging
import sys
import os
from datetime import timezone, datetime
from typing import List, Dict, Any

from models import FreeFoodEvent
from services.mq import Consumer
from services.config import REDIS_URL, MQ_STREAM
from services.notification.async_email import (
    create_email_provider,
    BatchEmailProcessor,
    EmailMessage,
)
from services.notification.email_templates import (
    EmailTemplateManager,
    UserPreferenceFilter,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


def _get_users_with_preferences() -> List[Dict[str, Any]]:
    """
    Get users with their preferences from database.

    Returns:
        List of user dictionaries with email and preferences
    """
    users = []

    # Try Supabase first
    try:
        from services.supabase_client import get_supabase_client

        supabase = get_supabase_client()

        # Get active users with their preferences
        response = (
            supabase.table("user_profiles")
            .select("id, email, notification_enabled, user_preferences(*)")
            .eq("notification_enabled", True)
            .execute()
        )

        if response.data:
            for user in response.data:
                prefs = user.get("user_preferences", [])
                user_prefs = prefs[0] if prefs else {}

                users.append(
                    {
                        "id": user["id"],
                        "email": user["email"],
                        "preferences": user_prefs,
                    }
                )

            logger.info(f"Loaded {len(users)} users from Supabase")
            return users

    except Exception as e:
        logger.warning(f"Failed to read from Supabase: {e}")

    # Fallback to legacy database
    try:
        from services.database import get_active_users

        emails = get_active_users()
        if emails:
            users = [
                {
                    "email": email,
                    "preferences": {},  # No preferences in legacy DB
                }
                for email in emails
            ]
            logger.info(f"Loaded {len(users)} users from legacy database")
            return users
    except Exception as e:
        logger.warning(f"Failed to read from legacy database: {e}")

    # Fallback to environment variable
    raw = os.environ.get("NOTIFICATION_RECIPIENTS", "")
    if raw:
        emails = [r.strip() for r in raw.split(",") if r.strip()]
        users = [{"email": email, "preferences": {}} for email in emails]
        logger.info(f"Loaded {len(users)} users from environment")
        return users

    logger.warning("No users found from any source")
    return []


def _get_email_config() -> dict:
    """Get Gmail SMTP configuration from environment variables."""
    return {
        "host": os.environ.get("SMTP_SERVER", "smtp.gmail.com"),
        "port": int(os.environ.get("SMTP_PORT", "465")),
        "username": os.environ.get("SMTP_USER", ""),
        "password": os.environ.get("SMTP_PASSWORD", ""),
        "use_ssl": os.environ.get("USE_SSL", "true").lower() == "true",
        "use_tls": os.environ.get("USE_STARTTLS", "false").lower() == "true",
        "from_email": os.environ.get("SMTP_USER", ""),
    }


def _get_batch_config() -> dict:
    """Get batch processing configuration from environment variables."""
    return {
        "batch_size": int(os.environ.get("EMAIL_BATCH_SIZE", "100")),
        "max_concurrent_batches": int(
            os.environ.get("EMAIL_MAX_CONCURRENT_BATCHES", "10")
        ),
        "rate_limit_per_second": float(
            os.environ.get("EMAIL_RATE_LIMIT_PER_SECOND", "10.0")
        ),
        "max_retries": int(os.environ.get("EMAIL_MAX_RETRIES", "3")),
    }


class AsyncNotificationProcessor:
    """Async notification processor with batch email delivery."""

    def __init__(
        self,
        email_processor: BatchEmailProcessor,
        template_manager: EmailTemplateManager,
    ):
        self.email_processor = email_processor
        self.template_manager = template_manager
        self.events_processed = 0
        self.events_failed = 0
        self.emails_sent = 0
        self.emails_failed = 0
        self.start_time = datetime.now(timezone.utc)

    def process_event(self, event: FreeFoodEvent) -> None:
        """
        Process event synchronously (called by MQ consumer).

        This is a sync wrapper around async processing.
        """
        try:
            logger.info(
                f"Processing event {event.event_id} — {event.title} @ {event.location}"
            )

            # Run async processing
            asyncio.run(self._process_event_async(event))

            self.events_processed += 1

        except Exception as e:
            self.events_failed += 1
            logger.error(
                f"Failed to process/notify for event {event.event_id}: {e}",
                exc_info=True,
            )
            raise

    async def _process_event_async(self, event: FreeFoodEvent) -> None:
        """Process event and send notifications asynchronously."""

        # Get users with preferences
        users = _get_users_with_preferences()

        if not users:
            logger.warning("No users found. Skipping notification.")
            return

        # Convert event to dict
        event_dict = event.model_dump()

        # Filter users based on preferences
        filtered_users = []
        for user in users:
            if UserPreferenceFilter.should_send_notification(
                user.get("preferences", {}), event_dict
            ):
                filtered_users.append(user)
            else:
                logger.debug(f"Skipping user {user['email']} based on preferences")

        if not filtered_users:
            logger.info("No users match notification criteria after filtering")
            return

        logger.info(
            f"Sending to {len(filtered_users)}/{len(users)} users after preference filtering"
        )

        # Render email template
        rendered = self.template_manager.render_single_event(event_dict)

        # Create email messages for all recipients
        messages = []
        for user in filtered_users:
            messages.append(
                EmailMessage(
                    to=user["email"],
                    subject=rendered["subject"],
                    html_body=rendered["html"],
                    metadata=event_dict,
                    notification_id=None,  # TODO: Create notification record
                )
            )

        # Send emails in batches
        logger.info(f"Sending {len(messages)} emails in batches...")

        results = await self.email_processor.send_all(messages)

        # Count results
        success_count = sum(1 for r in results if r.success)
        failed_count = len(results) - success_count

        self.emails_sent += success_count
        self.emails_failed += failed_count

        logger.info(
            f"✓ Event {event.event_id} processed: {success_count} sent, {failed_count} failed"
        )

        # TODO: Update notification records in database
        # TODO: Mark event as notified


def main():
    logger.info("=" * 60)
    logger.info("Starting Async Notification Service")
    logger.info("=" * 60)
    logger.info(f"Redis URL: {REDIS_URL}")
    logger.info(f"Stream: {MQ_STREAM}")

    # Get Gmail SMTP configuration
    email_config = _get_email_config()
    batch_config = _get_batch_config()

    logger.info("Email Provider: Gmail SMTP")
    logger.info(f"SMTP Server: {email_config['host']}:{email_config['port']}")
    logger.info(f"SMTP User: {email_config['username']}")
    logger.info(f"Use SSL: {email_config['use_ssl']}")

    # Check credentials
    if not email_config["username"] or not email_config["password"]:
        logger.warning("⚠️  SMTP_USER or SMTP_PASSWORD not set!")
        logger.warning("⚠️  Emails will fail to send.")
        logger.warning("⚠️  Please configure Gmail app password in .env file.")
        logger.warning(
            "⚠️  Learn how: https://support.google.com/accounts/answer/185833"
        )

    logger.info(f"Batch Size: {batch_config['batch_size']}")
    logger.info(f"Max Concurrent Batches: {batch_config['max_concurrent_batches']}")
    logger.info(f"Rate Limit: {batch_config['rate_limit_per_second']} emails/sec")
    logger.info(f"Max Retries: {batch_config['max_retries']}")

    # Create Gmail SMTP provider
    try:
        provider = create_email_provider(**email_config)
        logger.info("✅ Gmail SMTP provider created")
    except Exception as e:
        logger.error(f"❌ Failed to create Gmail SMTP provider: {e}")
        logger.error("Check your Gmail configuration in .env file")
        sys.exit(1)

    # Create batch processor
    try:
        email_processor = BatchEmailProcessor(provider, **batch_config)
        logger.info("✅ Batch email processor created")
    except Exception as e:
        logger.error(f"❌ Failed to create batch processor: {e}")
        sys.exit(1)

    # Create template manager
    try:
        template_manager = EmailTemplateManager()
        logger.info("✅ Email template manager created")
    except Exception as e:
        logger.error(f"❌ Failed to create template manager: {e}")
        logger.error(
            "Check that template files exist in services/notification/templates/"
        )
        sys.exit(1)

    # Create notification processor
    processor = AsyncNotificationProcessor(
        email_processor=email_processor,
        template_manager=template_manager,
    )

    # Create message queue consumer
    consumer = Consumer(
        redis_url=REDIS_URL,
        stream_name=MQ_STREAM,
        consumer_group="notification_service_group",
        consumer_name="notification_worker",
    )

    logger.info("=" * 60)
    logger.info("✅ Notification service ready — waiting for events...")
    logger.info("=" * 60)

    try:
        # Start consuming messages
        consumer.consume(handler=processor.process_event, block=5000, count=10)

    except KeyboardInterrupt:
        logger.info("\n" + "=" * 60)
        logger.info("Shutting down notification service (keyboard interrupt)")

        # Print statistics
        runtime = (datetime.now(timezone.utc) - processor.start_time).total_seconds()

        stats = {
            "runtime_seconds": round(runtime, 2),
            "events_processed": processor.events_processed,
            "events_failed": processor.events_failed,
            "emails_sent": processor.emails_sent,
            "emails_failed": processor.emails_failed,
            "avg_emails_per_event": (
                round(processor.emails_sent / processor.events_processed, 2)
                if processor.events_processed > 0
                else 0
            ),
        }

        logger.info(f"Final stats: {stats}")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Fatal error in notification service: {e}", exc_info=True)
        sys.exit(1)

    finally:
        # Cleanup
        try:
            asyncio.run(email_processor.close())
            logger.info("✅ Email processor closed")
        except Exception as e:
            logger.warning(f"Error closing email processor: {e}")

        consumer.close()
        logger.info("✅ Consumer closed")
        logger.info("Notification service stopped")


if __name__ == "__main__":
    main()
