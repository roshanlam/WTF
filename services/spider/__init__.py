"""
WTF Spider - Web crawler for detecting free food events.

This module provides an async web crawler that:
- Crawls event websites to find free food events
- Uses Gemini AI to verify free food mentions
- Stores confirmed events in Supabase database
- Publishes events to Redis for notification processing
"""

from services.spider.__main__ import (
    crawl_confirmed_free_food_events,
    crawl_confirmed_free_food_events_async,
    FreeFoodEvent,
    CrawlStatistics,
)

__all__ = [
    "crawl_confirmed_free_food_events",
    "crawl_confirmed_free_food_events_async",
    "FreeFoodEvent",
    "CrawlStatistics",
]
