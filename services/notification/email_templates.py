"""
Email template management for WTF notifications.

This module provides:
- Template loading from filesystem
- Template caching for performance
- Context building for events
- User preference filtering
"""

import logging
from datetime import datetime, time as dt_time
from pathlib import Path
from typing import Dict, Any, List, Optional
from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)

# Template directory
TEMPLATES_DIR = Path(__file__).parent / "templates"


class EmailTemplateManager:
    """Manages email templates and rendering."""

    def __init__(self, templates_dir: Optional[Path] = None):
        """
        Initialize template manager.

        Args:
            templates_dir: Path to templates directory (defaults to ./templates)
        """
        self.templates_dir = templates_dir or TEMPLATES_DIR

        if not self.templates_dir.exists():
            raise ValueError(f"Templates directory not found: {self.templates_dir}")

        # Create Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )

        logger.info(f"✅ Email templates loaded from {self.templates_dir}")

    def render_single_event(
        self,
        event: Dict[str, Any],
        unsubscribe_url: str = "#",
        feedback_url: str = "#",
    ) -> Dict[str, str]:
        """
        Render single event notification email.

        Args:
            event: Event data dictionary
            unsubscribe_url: URL for unsubscribe link
            feedback_url: URL for feedback link

        Returns:
            Dictionary with 'subject' and 'html' keys
        """
        template = self.env.get_template("single_event.html")

        # Build context
        context = {
            "title": event.get("title", "Free Food Event"),
            "location": event.get("location"),
            "start_time": self._format_datetime(event.get("start_time")),
            "description": event.get("description"),
            "llm_confidence": event.get("llm_confidence"),
            "unsubscribe_url": unsubscribe_url,
            "feedback_url": feedback_url,
        }

        # Render HTML
        html = template.render(**context)

        # Build subject line
        location = event.get("location", "TBD")
        subject = f"🍕 Free Food Alert: {event.get('title', 'Event')} at {location}"

        return {"subject": subject, "html": html}

    def render_digest(
        self,
        events: List[Dict[str, Any]],
        period: str = "Today",
        unsubscribe_url: str = "#",
        feedback_url: str = "#",
    ) -> Dict[str, str]:
        """
        Render digest email with multiple events.

        Args:
            events: List of event dictionaries
            period: Period description (e.g., "Today", "This Week")
            unsubscribe_url: URL for unsubscribe link
            feedback_url: URL for feedback link

        Returns:
            Dictionary with 'subject' and 'html' keys
        """
        template = self.env.get_template("digest.html")

        # Format events
        formatted_events = []
        for event in events:
            formatted_events.append(
                {
                    "title": event.get("title", "Free Food Event"),
                    "location": event.get("location"),
                    "start_time": self._format_datetime(event.get("start_time")),
                    "description": event.get("description"),
                    "llm_confidence": event.get("llm_confidence"),
                }
            )

        # Build context
        context = {
            "digest_title": f"{period} Free Food Digest",
            "period_description": period,
            "events": formatted_events,
            "unsubscribe_url": unsubscribe_url,
            "feedback_url": feedback_url,
        }

        # Render HTML
        html = template.render(**context)

        # Build subject line
        event_count = len(events)
        if event_count == 0:
            subject = f"📬 {period} Free Food Digest - No Events"
        elif event_count == 1:
            subject = f"📬 {period} Free Food Digest - 1 Event"
        else:
            subject = f"📬 {period} Free Food Digest - {event_count} Events"

        return {"subject": subject, "html": html}

    def _format_datetime(self, dt: Optional[Any]) -> Optional[str]:
        """
        Format datetime for display.

        Args:
            dt: datetime object or string

        Returns:
            Formatted string or None
        """
        if dt is None:
            return None

        # If already a string, return it
        if isinstance(dt, str):
            # Try to parse it
            try:
                dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                return dt

        # Format datetime
        if isinstance(dt, datetime):
            return dt.strftime("%A, %B %d at %I:%M %p")

        return str(dt)


class UserPreferenceFilter:
    """Filter events based on user preferences."""

    @staticmethod
    def should_send_notification(
        user_prefs: Dict[str, Any],
        event: Dict[str, Any],
        current_time: Optional[datetime] = None,
    ) -> bool:
        """
        Check if notification should be sent based on user preferences.

        Args:
            user_prefs: User preferences dictionary
            event: Event dictionary
            current_time: Current time (for testing, defaults to now)

        Returns:
            True if notification should be sent, False otherwise
        """
        current_time = current_time or datetime.now()

        # Check if notifications are enabled
        if not user_prefs.get("notification_enabled", True):
            logger.debug("Notifications disabled for user")
            return False

        # Check quiet hours
        quiet_start = user_prefs.get("quiet_hours_start")
        quiet_end = user_prefs.get("quiet_hours_end")

        if quiet_start and quiet_end:
            if UserPreferenceFilter._is_quiet_time(
                current_time.time(), quiet_start, quiet_end
            ):
                logger.debug(f"In quiet hours ({quiet_start} - {quiet_end})")
                return False

        # Check minimum confidence score
        min_confidence = user_prefs.get("min_confidence_score", 0.0)
        event_confidence = event.get("llm_confidence", 0.0)

        if event_confidence < min_confidence:
            logger.debug(
                f"Event confidence {event_confidence} below minimum {min_confidence}"
            )
            return False

        # Check event categories
        preferred_categories = user_prefs.get("preferred_categories")
        if preferred_categories:
            event_category = event.get("category")
            if event_category and event_category not in preferred_categories:
                logger.debug(
                    f"Event category {event_category} not in preferred {preferred_categories}"
                )
                return False

        return True

    @staticmethod
    def _is_quiet_time(current_time: dt_time, quiet_start: str, quiet_end: str) -> bool:
        """
        Check if current time is within quiet hours.

        Args:
            current_time: Current time
            quiet_start: Start of quiet hours (HH:MM format)
            quiet_end: End of quiet hours (HH:MM format)

        Returns:
            True if in quiet hours, False otherwise
        """
        try:
            # Parse quiet hours
            start_hour, start_min = map(int, quiet_start.split(":"))
            end_hour, end_min = map(int, quiet_end.split(":"))

            start = dt_time(start_hour, start_min)
            end = dt_time(end_hour, end_min)

            # Handle overnight quiet hours (e.g., 22:00 - 08:00)
            if start <= end:
                return start <= current_time <= end
            else:
                return current_time >= start or current_time <= end

        except (ValueError, AttributeError) as e:
            logger.warning(f"Invalid quiet hours format: {e}")
            return False


class DigestBuilder:
    """Build digest emails by batching events."""

    def __init__(self, template_manager: EmailTemplateManager):
        """
        Initialize digest builder.

        Args:
            template_manager: EmailTemplateManager instance
        """
        self.template_manager = template_manager

    def build_daily_digest(
        self, events: List[Dict[str, Any]], date: Optional[datetime] = None
    ) -> Dict[str, str]:
        """
        Build daily digest email.

        Args:
            events: List of events
            date: Date for digest (defaults to today)

        Returns:
            Dictionary with 'subject' and 'html' keys
        """
        date = date or datetime.now()
        period = date.strftime("%A, %B %d")

        return self.template_manager.render_digest(events, period=period)

    def build_weekly_digest(
        self, events: List[Dict[str, Any]], week_start: Optional[datetime] = None
    ) -> Dict[str, str]:
        """
        Build weekly digest email.

        Args:
            events: List of events
            week_start: Start of week (defaults to current week)

        Returns:
            Dictionary with 'subject' and 'html' keys
        """
        week_start = week_start or datetime.now()
        period = f"Week of {week_start.strftime('%B %d')}"

        return self.template_manager.render_digest(events, period=period)

    def group_events_by_user_preference(
        self,
        events: List[Dict[str, Any]],
        users: List[Dict[str, Any]],
        current_time: Optional[datetime] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Group events by user based on preferences.

        Args:
            events: List of events
            users: List of user dictionaries with preferences
            current_time: Current time (for testing)

        Returns:
            Dictionary mapping user IDs to list of events
        """
        user_events: Dict[str, List[Dict[str, Any]]] = {}

        for user in users:
            user_id = user.get("id") or user.get("email")
            if not user_id:
                continue

            user_prefs = user.get("preferences", {})

            # Filter events for this user
            filtered_events = [
                event
                for event in events
                if UserPreferenceFilter.should_send_notification(
                    user_prefs, event, current_time
                )
            ]

            if filtered_events:
                user_events[str(user_id)] = filtered_events

        return user_events
