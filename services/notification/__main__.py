import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from dotenv import load_dotenv
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

# Import your teammate's FreeFoodEvent model
from models import FreeFoodEvent

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class NotificationService:
    """
    Twilio SMS Notification Service for food events
    
    Compatible with Redis Streams and FreeFoodEvent model
    """
    
    def __init__(self):
        """Initialize Twilio client and configuration"""
        self.account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        self.auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        self.from_number = os.getenv('TWILIO_PHONE_NUMBER')
        self.to_numbers = self._parse_recipient_numbers()
        
        # Notification settings
        self.min_confidence = float(os.getenv('MIN_CONFIDENCE_THRESHOLD', '0.5'))
        
        # Validate configuration
        if not all([self.account_sid, self.auth_token, self.from_number]):
            raise ValueError(
                "Missing Twilio credentials. Please set TWILIO_ACCOUNT_SID, "
                "TWILIO_AUTH_TOKEN, and TWILIO_PHONE_NUMBER in environment variables"
            )
        
        if not self.to_numbers:
            logger.warning(
                "[NOTIFICATION] No recipient numbers configured. "
                "Set TWILIO_TO_NUMBERS in environment variables"
            )
        
        # Initialize Twilio client
        try:
            self.client = Client(self.account_sid, self.auth_token)
            logger.info("[NOTIFICATION] Twilio client initialized successfully")
        except Exception as e:
            logger.error(f"[NOTIFICATION] Failed to initialize Twilio client: {str(e)}")
            raise
    
    def _parse_recipient_numbers(self) -> list:
        """Parse recipient phone numbers from environment variable"""
        numbers_str = os.getenv('TWILIO_TO_NUMBERS', '')
        if not numbers_str:
            return []
        
        numbers = [num.strip() for num in numbers_str.split(',') if num.strip()]
        logger.info(f"[NOTIFICATION] Configured {len(numbers)} recipient(s)")
        return numbers
    
    def _format_message(self, event: FreeFoodEvent) -> str:
        """
        Format FreeFoodEvent into SMS message
        
        Args:
            event: FreeFoodEvent model instance
            
        Returns:
            Formatted SMS message string
        """
        title = event.title or 'Food Event'
        location = event.location or 'Location TBD'
        source = event.source or 'Unknown'
        
        # Format time if available
        formatted_time = 'Time TBD'
        if event.start_time:
            try:
                formatted_time = event.start_time.strftime('%b %d at %I:%M %p')
            except Exception:
                formatted_time = str(event.start_time)
        
        # Build message
        message = f"""🍕 FREE FOOD ALERT! 🍕

{title}
{source}

📍 Location: {location}
🕐 Time: {formatted_time}

Don't miss out!"""

        # Add confidence if available and below threshold
        if event.llm_confidence and event.llm_confidence < 0.8:
            message += f"\n\n⚠️ Confidence: {event.llm_confidence:.0%}"
        
        return message
    
    def _send_sms(self, to_number: str, message: str) -> tuple[bool, Optional[str]]:
        """
        Send SMS via Twilio
        
        Args:
            to_number: Recipient phone number
            message: Message body
            
        Returns:
            Tuple of (success, message_sid or error)
        """
        try:
            logger.info(f"[NOTIFICATION] Sending SMS to {to_number}")
            
            twilio_message = self.client.messages.create(
                body=message,
                from_=self.from_number,
                to=to_number
            )
            
            logger.info(
                f"[NOTIFICATION] ✓ SMS sent successfully - SID: {twilio_message.sid}"
            )
            return True, twilio_message.sid
            
        except TwilioRestException as e:
            logger.error(
                f"[NOTIFICATION] Twilio API error: {e.code} - {e.msg}"
            )
            return False, f"Twilio error: {e.msg}"
            
        except Exception as e:
            logger.error(f"[NOTIFICATION] Failed to send SMS: {str(e)}")
            return False, str(e)
    
    def should_notify(self, event: FreeFoodEvent) -> tuple[bool, str]:
        """
        Determine if an event should trigger notifications
        
        Args:
            event: FreeFoodEvent to evaluate
            
        Returns:
            Tuple of (should_notify, reason)
        """
        # Check confidence threshold
        if event.llm_confidence is not None:
            if event.llm_confidence < self.min_confidence:
                return False, f"Confidence too low: {event.llm_confidence:.2f} < {self.min_confidence}"
        
        # Check if event has required fields
        if not event.title:
            return False, "Missing event title"
        
        if not event.location:
            return False, "Missing event location"
        
        # All checks passed
        return True, "Event meets notification criteria"
    
    def send_notification(self, event: FreeFoodEvent) -> bool:
        """
        Main notification handler - compatible with Redis consumer
        
        Args:
            event: FreeFoodEvent model instance
            
        Returns:
            bool: True if at least one notification sent successfully
        """
        logger.info(
            f"[NOTIFICATION] Processing event: {event.event_id} | "
            f"Title: {event.title} | Source: {event.source}"
        )
        
        # Check if we should notify
        should_notify, reason = self.should_notify(event)
        if not should_notify:
            logger.info(f"[NOTIFICATION] Skipping notification: {reason}")
            return True  # Return True to acknowledge the message
        
        logger.info(f"[NOTIFICATION] Notification approved: {reason}")
        
        # Check if we have recipients
        if not self.to_numbers:
            logger.error("[NOTIFICATION] No recipient numbers configured")
            return False
        
        # Format message
        try:
            message = self._format_message(event)
            logger.debug(f"[NOTIFICATION] Formatted message:\n{message}")
        except Exception as e:
            logger.error(f"[NOTIFICATION] Failed to format message: {str(e)}")
            return False
        
        # Send to all recipients
        success_count = 0
        failure_count = 0
        
        for to_number in self.to_numbers:
            success, result = self._send_sms(to_number, message)
            if success:
                success_count += 1
            else:
                failure_count += 1
                logger.error(f"[NOTIFICATION] Failed to send to {to_number}: {result}")
        
        logger.info(
            f"[NOTIFICATION] Batch complete for {event.event_id}: "
            f"{success_count} sent, {failure_count} failed"
        )
        
        # Return True if at least one message was sent successfully
        return success_count > 0
    
    def send_test_notification(self):
        """Send a test notification to verify Twilio integration"""
        logger.info("[NOTIFICATION] Sending test notification...")
        
        if not self.to_numbers:
            logger.error("[NOTIFICATION] No recipient numbers configured for test")
            return
        
        # Create a test event with all required fields
        test_event = FreeFoodEvent(
            event_id="test_001",
            title="Test Event - Free Pizza",
            location="Computer Science Building",
            start_time=datetime.now(timezone.utc),
            source="Test System",
            llm_confidence=1.0,
            reason="This is a test notification",
            published_at=datetime.now(timezone.utc)
        )
        
        self.send_notification(test_event)


def main():
    """
    Main entry point for Notification Service
    Can be run standalone for testing
    """
    print("=" * 80)
    print("NOTIFICATION SERVICE (TWILIO)")
    print("=" * 80)
    print()
    
    try:
        notification_service = NotificationService()
        
        print(f"Min confidence threshold: {notification_service.min_confidence}")
        print(f"Recipients configured: {len(notification_service.to_numbers)}")
        print()
        
        # Send test notification
        print("Sending test notification...")
        notification_service.send_test_notification()
        
        print("\n" + "=" * 80)
        print("Service initialized successfully!")
        print("Ready to receive events from Redis consumer")
        print("=" * 80)
        
    except ValueError as e:
        logger.error(f"Configuration error: {str(e)}")
        print("\nPlease configure the following environment variables:")
        print("- TWILIO_ACCOUNT_SID")
        print("- TWILIO_AUTH_TOKEN")
        print("- TWILIO_PHONE_NUMBER (your Twilio number)")
        print("- TWILIO_TO_NUMBERS (comma-separated recipient numbers)")
        print("- MIN_CONFIDENCE_THRESHOLD (optional, default: 0.5)")
        
    except Exception as e:
        logger.error(f"Failed to initialize service: {str(e)}")


if __name__ == "__main__":
    main()