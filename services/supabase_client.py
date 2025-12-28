"""Supabase client for WTF application."""

import logging
import os
from typing import Any, Dict, List, Optional

from postgrest.exceptions import APIError

from supabase import Client, create_client  # type: ignore[attr-defined]

logger = logging.getLogger(__name__)

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")  # Service role for backend
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")  # Public anon key for client

# Global Supabase client
_supabase: Optional[Client] = None


def get_supabase_client() -> Client:
    """Get or create Supabase client instance."""
    global _supabase

    if _supabase is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in environment"
            )

        _supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("✅ Supabase client initialized")

    return _supabase


def get_anon_client() -> Client:
    """Get Supabase client with anonymous key (for public access)."""
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise ValueError(
            "SUPABASE_URL and SUPABASE_ANON_KEY must be set in environment"
        )

    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


# ============================================
# User Operations
# ============================================


def add_user_subscription(email: str) -> Optional[Dict[str, Any]]:
    """
    Subscribe a user (sign them up via Supabase Auth).

    Note: This should typically be done via Supabase Auth signup flow.
    This function is for backend-initiated subscriptions.
    """
    try:
        supabase = get_supabase_client()

        # Check if user already exists
        existing = (
            supabase.table("user_profiles")
            .select("id, email")
            .eq("email", email)
            .execute()
        )

        if existing.data:
            logger.info(f"User {email} already subscribed")
            return existing.data[0]

        # For backend subscription, we need to create auth user first
        # This uses admin API (service role key required)
        auth_response = supabase.auth.admin.create_user({"email": email})

        if auth_response.user:
            logger.info(f"✅ User {email} subscribed successfully")
            return {"id": auth_response.user.id, "email": email}
        else:
            logger.error(f"Failed to create user {email}")
            return None

    except APIError as e:
        logger.error(f"Supabase API error subscribing {email}: {e}")
        return None
    except Exception as e:
        logger.error(f"Error subscribing {email}: {e}")
        return None


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Get user profile by email."""
    try:
        supabase = get_supabase_client()
        response = (
            supabase.table("user_profiles")
            .select("*")
            .eq("email", email)
            .single()
            .execute()
        )
        return response.data if response.data else None
    except Exception as e:
        logger.error(f"Error fetching user {email}: {e}")
        return None


def get_active_users() -> List[str]:
    """Get all active user emails (for notifications)."""
    try:
        supabase = get_supabase_client()

        # Use the helper function we created
        response = supabase.rpc("get_active_subscribers").execute()

        if response.data:
            # Return list of emails
            return [user["email"] for user in response.data]
        return []

    except Exception as e:
        logger.error(f"Error fetching active users: {e}")
        return []


def deactivate_user(email: str) -> bool:
    """Deactivate a user subscription."""
    try:
        supabase = get_supabase_client()

        # Update user profile to disable notifications
        response = (
            supabase.table("user_profiles")
            .update({"notification_enabled": False})
            .eq("email", email)
            .execute()
        )

        return len(response.data) > 0
    except Exception as e:
        logger.error(f"Error deactivating user {email}: {e}")
        return False


def update_user_preferences(
    user_id: str, preferences: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Update user notification preferences."""
    try:
        supabase = get_supabase_client()

        response = (
            supabase.table("user_preferences")
            .update(preferences)
            .eq("user_id", user_id)
            .execute()
        )

        return response.data[0] if response.data else None
    except Exception as e:
        logger.error(f"Error updating preferences for user {user_id}: {e}")
        return None


# ============================================
# Event Operations
# ============================================


def add_event(
    title: str,
    description: str,
    location: str,
    event_date: str,
    source_id: int,
    has_free_food: bool = False,
    confidence_score: Optional[float] = None,
    **kwargs,
) -> Optional[Dict[str, Any]]:
    """Add a new event to the database."""
    try:
        supabase = get_supabase_client()

        event_data = {
            "title": title,
            "description": description,
            "location": location,
            "event_date": event_date,
            "source_id": source_id,
            "has_free_food": has_free_food,
            "confidence_score": confidence_score,
            **kwargs,
        }

        response = supabase.table("events").insert(event_data).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        logger.error(f"Error adding event: {e}")
        return None


def get_event(event_id: int) -> Optional[Dict[str, Any]]:
    """Get event by ID."""
    try:
        supabase = get_supabase_client()
        response = (
            supabase.table("events").select("*").eq("id", event_id).single().execute()
        )
        return response.data if response.data else None
    except Exception as e:
        logger.error(f"Error fetching event {event_id}: {e}")
        return None


def get_events(
    limit: int = 100,
    has_free_food: Optional[bool] = None,
    notification_sent: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """Get events with optional filters."""
    try:
        supabase = get_supabase_client()

        query = supabase.table("events").select("*")

        if has_free_food is not None:
            query = query.eq("has_free_food", has_free_food)

        if notification_sent is not None:
            query = query.eq("notification_sent", notification_sent)

        response = query.order("event_date", desc=True).limit(limit).execute()

        return response.data if response.data else []
    except Exception as e:
        logger.error(f"Error fetching events: {e}")
        return []


def get_recent_food_events(days: int = 1, limit: int = 50) -> List[Dict[str, Any]]:
    """Get recent free food events using the view."""
    try:
        supabase = get_supabase_client()

        # Use the view we created
        response = (
            supabase.table("v_recent_food_events").select("*").limit(limit).execute()
        )

        return response.data if response.data else []
    except Exception as e:
        logger.error(f"Error fetching recent food events: {e}")
        return []


def mark_event_notified(event_id: int, notification_count: int = 0) -> bool:
    """Mark an event as notified."""
    try:
        supabase = get_supabase_client()

        response = (
            supabase.table("events")
            .update(
                {
                    "notification_sent": True,
                    "notification_sent_at": "now()",
                    "notification_count": notification_count,
                }
            )
            .eq("id", event_id)
            .execute()
        )

        return len(response.data) > 0
    except Exception as e:
        logger.error(f"Error marking event {event_id} as notified: {e}")
        return False


def search_events(query: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Full-text search for events."""
    try:
        supabase = get_supabase_client()

        # Use the search function we created
        response = supabase.rpc(
            "search_events", {"search_query": query, "limit_count": limit}
        ).execute()

        return response.data if response.data else []
    except Exception as e:
        logger.error(f"Error searching events: {e}")
        return []


# ============================================
# Notification Operations
# ============================================


def add_notification(
    user_id: str,
    event_id: int,
    channel: str = "email",
    email_subject: Optional[str] = None,
    **kwargs,
) -> Optional[Dict[str, Any]]:
    """Add a notification record."""
    try:
        supabase = get_supabase_client()

        notification_data = {
            "user_id": user_id,
            "event_id": event_id,
            "channel": channel,
            "status": "pending",
            "email_subject": email_subject,
            **kwargs,
        }

        response = supabase.table("notifications").insert(notification_data).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        logger.error(f"Error adding notification: {e}")
        return None


def update_notification_status(notification_id: int, status: str, **kwargs) -> bool:
    """Update notification status (sent, delivered, opened, etc.)."""
    try:
        supabase = get_supabase_client()

        update_data = {"status": status, **kwargs}

        response = (
            supabase.table("notifications")
            .update(update_data)
            .eq("id", notification_id)
            .execute()
        )

        return len(response.data) > 0
    except Exception as e:
        logger.error(f"Error updating notification {notification_id}: {e}")
        return False


def get_user_notifications(user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Get notifications for a user."""
    try:
        supabase = get_supabase_client()

        response = (
            supabase.table("notifications")
            .select("*")
            .eq("user_id", user_id)
            .order("sent_at", desc=True)
            .limit(limit)
            .execute()
        )

        return response.data if response.data else []
    except Exception as e:
        logger.error(f"Error fetching notifications for user {user_id}: {e}")
        return []


# ============================================
# Event Sources & Categories
# ============================================


def get_event_sources(active_only: bool = True) -> List[Dict[str, Any]]:
    """Get event sources."""
    try:
        supabase = get_supabase_client()

        query = supabase.table("event_sources").select("*")

        if active_only:
            query = query.eq("is_active", True)

        response = query.order("priority", desc=True).execute()
        return response.data if response.data else []
    except Exception as e:
        logger.error(f"Error fetching event sources: {e}")
        return []


def get_event_categories(active_only: bool = True) -> List[Dict[str, Any]]:
    """Get event categories."""
    try:
        supabase = get_supabase_client()

        query = supabase.table("event_categories").select("*")

        if active_only:
            query = query.eq("is_active", True)

        response = query.order("display_order").execute()
        return response.data if response.data else []
    except Exception as e:
        logger.error(f"Error fetching event categories: {e}")
        return []


# ============================================
# Statistics & Analytics
# ============================================


def get_stats() -> Dict[str, Any]:
    """Get database statistics."""
    try:
        supabase = get_supabase_client()

        # Get counts using simple queries
        events_response = supabase.table("events").select("id", count="exact").execute()

        food_events_response = (
            supabase.table("events")
            .select("id", count="exact")
            .eq("has_free_food", True)
            .execute()
        )

        users_response = (
            supabase.table("user_profiles")
            .select("id", count="exact")
            .eq("notification_enabled", True)
            .execute()
        )

        return {
            "total_events": events_response.count or 0,
            "food_events": food_events_response.count or 0,
            "active_users": users_response.count or 0,
        }
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        return {
            "total_events": 0,
            "food_events": 0,
            "active_users": 0,
        }


# ============================================
# Helper: Invalidate cache (for compatibility)
# ============================================


def invalidate_users_cache():
    """
    Invalidate users cache.

    Note: With Supabase, we don't need Redis caching for users
    because Supabase has built-in caching and is fast enough.
    This function is kept for compatibility with existing code.
    """
    logger.info("Cache invalidation called (no-op with Supabase)")
    pass
