# WTF Project - Issues & Implementation Roadmap

---

## 🔴 **Critical Issues (Must Fix Before Production)**

### Issue #1: Spider Database Upsert Constraint Missing

**Priority:** 🔴 Critical
**Type:** Bug
**Component:** Spider, Database

**Problem:**
The spider cannot use `upsert()` to avoid duplicate events because the required unique constraint doesn't exist on the `events` table.

**Current Behavior:**
```python
# services/spider/__main__.py:565-569
response = (
    supabase.table("events")
    .upsert(event_data, on_conflict="external_source_id,source_id")
    .execute()
)
```

**Error:**
```
{'message': 'there is no unique or exclusion constraint matching the ON CONFLICT specification', 'code': '42P10'}
```

**Root Cause:**
The `events` table is missing a unique constraint on `(external_source_id, source_id)`.

**Solution:**
1. Create a database migration to add the constraint:

```sql
-- supabase/migrations/YYYYMMDDHHMMSS_add_event_unique_constraint.sql
ALTER TABLE events
ADD CONSTRAINT events_external_source_unique
UNIQUE (external_source_id, source_id);

-- Handle existing duplicates first
DELETE FROM events a USING events b
WHERE a.id > b.id
AND a.external_source_id = b.external_source_id
AND a.source_id = b.source_id;
```

2. Update the spider to use upsert properly:

```python
response = (
    supabase.table("events")
    .upsert(
        event_data,
        on_conflict="external_source_id,source_id",
        returning="representation"
    )
    .execute()
)
```

**Impact:** High - Currently creates duplicate events on every spider run

**Estimated Effort:** 2 hours

---

### Issue #2: Scraper Not Saving to Database

**Priority:** 🔴 Critical
**Type:** Missing Feature
**Component:** Scraper

**Problem:**
The UMass scraper (`services/scrape/__main__.py`) only saves events to JSON files, not to the Supabase database. Events are not integrated into the notification system.

**Current Behavior:**
```python
# services/scrape/__main__.py:256-257
output_file = scraper.save_events(events)  # Saves to JSON only
logger.info(f"Successfully scraped {len(events)} events")
```

**Expected Behavior:**
Events should be saved to Supabase `events` table with:
- Proper source tracking
- Free food detection
- Confidence scores
- Integration with notification pipeline

**Solution:**

1. Add database integration to the scraper:

```python
# services/scrape/__main__.py

from services.supabase_client import get_supabase_client

def save_event_to_database(self, event: Dict, source_id: int) -> Optional[int]:
    """Save scraped event to Supabase database."""
    try:
        supabase = get_supabase_client()

        # Parse dates
        start_date = None
        if event.get('instances'):
            start_date = event['instances'][0].get('start')

        # Determine free food status and confidence
        has_free_food = event.get('is_free', False) and any(
            keyword in event.get('description_text', '').lower() + event.get('title', '').lower()
            for keyword in self.food_keywords
        )

        confidence = 0.8 if event.get('food_confidence') == 'high' else 0.6

        event_data = {
            "title": event.get('title', '')[:500],
            "description": event.get('description_text', '')[:5000],
            "location": event.get('location', {}).get('name', '')[:500] if event.get('location') else None,
            "event_date": start_date,
            "source_id": source_id,
            "source_url": event.get('url'),
            "external_source_id": str(event.get('id')),
            "has_free_food": has_free_food,
            "confidence_score": confidence if has_free_food else 0.0,
            "classification_reason": f"Keyword match: {event.get('food_confidence', 'none')}",
            "raw_data": event,
        }

        response = supabase.table("events").upsert(
            event_data,
            on_conflict="external_source_id,source_id"
        ).execute()

        if response.data:
            return response.data[0].get("id")
        return None
    except Exception as e:
        logger.error(f"Error saving event to database: {e}")
        return None
```

2. Create a source for the scraper:

```python
def get_or_create_scraper_source() -> int:
    """Get or create UMass scraper event source."""
    try:
        supabase = get_supabase_client()

        response = (
            supabase.table("event_sources")
            .select("id")
            .eq("name", "UMass Events Calendar Scraper")
            .execute()
        )

        if response.data:
            return response.data[0]["id"]

        source_data = {
            "name": "UMass Events Calendar Scraper",
            "type": "api",
            "source_identifier": "umass-localist-api",
            "is_active": True,
            "is_verified": True,
            "trust_score": 95,
            "priority": 20,
            "description": "Official UMass Events Calendar via Localist API",
        }

        response = supabase.table("event_sources").insert(source_data).execute()
        return response.data[0]["id"]
    except Exception as e:
        logger.warning(f"Could not get/create scraper source: {e}")
        return 1
```

3. Update main() to save to database:

```python
def main():
    scraper = UMassEventsScraper()
    source_id = get_or_create_scraper_source()

    events = scraper.fetch_events(days_ahead=7)

    if events:
        saved_count = 0
        for event in events:
            event_id = save_event_to_database(event, source_id)
            if event_id:
                saved_count += 1

        logger.info(f"Saved {saved_count}/{len(events)} events to database")
```

**Impact:** High - Scraper is not integrated with notification system

**Estimated Effort:** 4 hours

---

### Issue #3: Missing Event Deduplication Across Sources

**Priority:** 🔴 Critical
**Type:** Missing Feature
**Component:** Database, Spider, Scraper

**Problem:**
The same event can be detected by both the spider and scraper, creating duplicates with different `external_source_id` values.

**Example:**
- Spider finds: "CS Club Pizza Night" from https://events.umass.edu/event/123
- Scraper finds: Same event from Localist API with ID "456789"
- Result: Two separate database entries for the same event

**Solution:**

1. Add fuzzy matching function:

```python
# services/event_deduplication.py

from difflib import SequenceMatcher
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from services.supabase_client import get_supabase_client

def find_similar_events(
    title: str,
    event_date: str,
    location: str,
    threshold: float = 0.85
) -> Optional[int]:
    """
    Find existing events that are likely duplicates.

    Args:
        title: Event title
        event_date: ISO datetime string
        location: Event location
        threshold: Similarity threshold (0-1)

    Returns:
        Event ID if duplicate found, None otherwise
    """
    try:
        supabase = get_supabase_client()

        # Parse event date
        event_dt = datetime.fromisoformat(event_date.replace('Z', '+00:00'))

        # Query events within 2 hours of this event
        time_window_start = (event_dt - timedelta(hours=2)).isoformat()
        time_window_end = (event_dt + timedelta(hours=2)).isoformat()

        result = supabase.table("events")\
            .select("id, title, location, event_date")\
            .gte("event_date", time_window_start)\
            .lte("event_date", time_window_end)\
            .execute()

        # Check for similar titles and locations
        for event in result.data:
            title_similarity = SequenceMatcher(
                None,
                title.lower().strip(),
                event['title'].lower().strip()
            ).ratio()

            location_similarity = SequenceMatcher(
                None,
                (location or "").lower().strip(),
                (event.get('location') or "").lower().strip()
            ).ratio()

            # If both title and location are very similar, it's likely a duplicate
            if title_similarity >= threshold and location_similarity >= 0.7:
                return event['id']

        return None
    except Exception as e:
        print(f"Error checking for duplicates: {e}")
        return None


def merge_event_data(existing_id: int, new_data: Dict) -> bool:
    """
    Update existing event with additional data from new source.

    Args:
        existing_id: ID of existing event
        new_data: New event data to merge

    Returns:
        True if merge successful
    """
    try:
        supabase = get_supabase_client()

        # Get existing event
        existing = supabase.table("events")\
            .select("*")\
            .eq("id", existing_id)\
            .single()\
            .execute()

        if not existing.data:
            return False

        # Merge logic: keep higher confidence, combine descriptions, etc.
        updates = {}

        # Update confidence if new source has higher confidence
        if new_data.get('confidence_score', 0) > existing.data.get('confidence_score', 0):
            updates['confidence_score'] = new_data['confidence_score']
            updates['classification_reason'] = new_data.get('classification_reason')

        # Append to raw_data to track all sources
        raw_data = existing.data.get('raw_data', {})
        if not isinstance(raw_data, dict):
            raw_data = {}

        raw_data['additional_sources'] = raw_data.get('additional_sources', [])
        raw_data['additional_sources'].append({
            'source_id': new_data.get('source_id'),
            'external_source_id': new_data.get('external_source_id'),
            'url': new_data.get('source_url'),
            'detected_at': datetime.now().isoformat(),
        })
        updates['raw_data'] = raw_data

        # Update the event
        supabase.table("events").update(updates).eq("id", existing_id).execute()

        return True
    except Exception as e:
        print(f"Error merging event data: {e}")
        return False
```

2. Update spider and scraper to use deduplication:

```python
# Before inserting/upserting
from services.event_deduplication import find_similar_events, merge_event_data

duplicate_id = find_similar_events(
    title=event_data['title'],
    event_date=event_data['event_date'],
    location=event_data.get('location', '')
)

if duplicate_id:
    logger.info(f"Found duplicate event (ID: {duplicate_id}), merging data...")
    merge_event_data(duplicate_id, event_data)
else:
    # Insert new event
    response = supabase.table("events").insert(event_data).execute()
```

**Impact:** High - Prevents spam notifications for duplicate events

**Estimated Effort:** 6 hours

---

## 🟡 **High Priority Issues**

### Issue #4: Async Test Failures

**Priority:** 🟡 High
**Type:** Bug
**Component:** Tests

**Problem:**
3 tests are failing because they use `async def` but pytest-asyncio is not installed.

**Failing Tests:**
1. `scripts/test_batch_email.py::test_batch_email`
2. `scripts/test_email.py::test_email_send`
3. `tests/test_integration_demo.py::test_consume`

**Error:**
```
Failed: async def functions are not natively supported.
You need to install a suitable plugin for your async framework, for example:
  - anyio
  - pytest-asyncio
```

**Solution:**

1. Add pytest-asyncio to dev dependencies:

```bash
poetry add --group dev pytest-asyncio
```

2. Configure pytest to use asyncio:

```python
# pyproject.toml

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

3. Or add decorator to async tests:

```python
import pytest

@pytest.mark.asyncio
async def test_batch_email():
    # Test code...
```

**Impact:** Medium - Tests don't run properly

**Estimated Effort:** 1 hour

---

### Issue #5: Linting Issues in Scraper

**Priority:** 🟡 High
**Type:** Code Quality
**Component:** Scraper

**Problem:**
Minor linting issues that should be fixed:

1. **Unused import** in `services/scrape/__main__.py:9`
   - `timedelta` imported but never used

2. **Unused variable** in `services/scrape/__main__.py:256`
   - `output_file` assigned but never used

**Solution:**

```python
# services/scrape/__main__.py

# Fix 1: Remove unused import
from datetime import datetime  # Remove ", timedelta"

# Fix 2: Remove unused variable assignment
if events:
    # Save all events
    scraper.save_events(events)  # Don't assign to output_file
    logger.info(f"Successfully scraped {len(events)} events")
```

Or use the variable:

```python
if events:
    output_file = scraper.save_events(events)
    logger.info(f"Successfully scraped {len(events)} events to {output_file}")
```

**Auto-fix:**
```bash
poetry run ruff check --fix .
```

**Impact:** Low - Code quality issue

**Estimated Effort:** 15 minutes

---

### Issue #6: Supabase Client Requires Manual Dotenv Override

**Priority:** 🟡 High
**Type:** Bug
**Component:** Supabase Client

**Problem:**
The Supabase client requires explicit `load_dotenv(override=True)` before importing, which is error-prone and causes issues in different contexts.

**Current Workaround:**
```python
# This works
from dotenv import load_dotenv
load_dotenv(override=True)
from services.supabase_client import get_supabase_client

# This doesn't work
from services.supabase_client import get_supabase_client  # Variables not loaded
```

**Root Cause:**
The `supabase_client.py` loads environment variables at import time, but the `.env` file might not be loaded yet.

**Solution:**

1. Lazy load environment variables in the client:

```python
# services/supabase_client.py

import logging
import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from postgrest.exceptions import APIError
from supabase import Client, create_client

logger = logging.getLogger(__name__)

# Global Supabase client
_supabase: Optional[Client] = None
_config_loaded = False


def _load_config():
    """Load environment configuration once."""
    global _config_loaded
    if not _config_loaded:
        load_dotenv(override=True)
        _config_loaded = True


def get_supabase_client() -> Client:
    """Get or create Supabase client instance."""
    global _supabase

    _load_config()  # Ensure config is loaded

    if _supabase is None:
        SUPABASE_URL = os.getenv("SUPABASE_API_URL") or os.getenv("SUPABASE_URL", "")
        SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

        # Validate URL format
        if SUPABASE_URL and SUPABASE_URL.startswith("postgresql://"):
            logger.warning(
                "SUPABASE_URL appears to be a postgres connection string. "
                "Set SUPABASE_API_URL to your Supabase API URL (https://xxx.supabase.co)"
            )
            SUPABASE_URL = ""

        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in environment"
            )

        _supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("✅ Supabase client initialized")

    return _supabase
```

**Impact:** Medium - Makes code more robust

**Estimated Effort:** 1 hour

---

### Issue #7: No Automated Scheduling System

**Priority:** 🟡 High
**Type:** Missing Feature
**Component:** Infrastructure

**Problem:**
Spider and scraper must be run manually. No automated scheduling is implemented.

**Current State:**
- Users must manually run `poetry run scrape` or `poetry run spider`
- README suggests cron jobs but doesn't provide ready-to-use scripts
- No monitoring or error handling for scheduled runs

**Solution:**

1. Create a scheduling service:

```python
# services/scheduler/__main__.py

import asyncio
import logging
import schedule
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(override=True)

from services.scrape.__main__ import main as run_scraper
from services.spider.__main__ import crawl_confirmed_free_food_events
from services.supabase_client import get_supabase_client

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_daily_scrape():
    """Run the scraper daily."""
    try:
        logger.info("Starting daily UMass Events scrape...")
        run_scraper()
        logger.info("✅ Daily scrape completed successfully")
    except Exception as e:
        logger.error(f"❌ Daily scrape failed: {e}")
        # TODO: Send alert email/SMS


def run_weekly_spider():
    """Run the spider weekly."""
    try:
        logger.info("Starting weekly AI spider crawl...")
        events = crawl_confirmed_free_food_events(
            seed_url="https://events.umass.edu",
            days_lookahead=14,
            max_pages=200,
            save_to_db=True
        )
        logger.info(f"✅ Weekly spider completed. Found {len(events)} events")
    except Exception as e:
        logger.error(f"❌ Weekly spider failed: {e}")
        # TODO: Send alert email/SMS


def check_database_health():
    """Check database connection and log stats."""
    try:
        supabase = get_supabase_client()

        # Check recent events
        result = supabase.table('events')\
            .select('id', count='exact')\
            .eq('has_free_food', True)\
            .execute()

        logger.info(f"📊 Database health: {result.count} free food events")
    except Exception as e:
        logger.error(f"❌ Database health check failed: {e}")


def main():
    """Main scheduler loop."""
    logger.info("🚀 WTF Event Scheduler starting...")

    # Schedule jobs
    schedule.every().day.at("06:00").do(run_daily_scrape)
    schedule.every().sunday.at("07:00").do(run_weekly_spider)
    schedule.every().hour.do(check_database_health)

    # Run initial health check
    check_database_health()

    logger.info("📅 Scheduler running. Jobs:")
    for job in schedule.get_jobs():
        logger.info(f"  - {job}")

    # Main loop
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute


if __name__ == "__main__":
    main()
```

2. Add dependencies:

```bash
poetry add schedule
```

3. Create systemd service file:

```ini
# /etc/systemd/system/wtf-scheduler.service

[Unit]
Description=WTF Event Scheduler
After=network.target

[Service]
Type=simple
User=wtf
WorkingDirectory=/path/to/wtf
ExecStart=/path/to/wtf/venv/bin/python -m services.scheduler
Restart=always
RestartSec=10
Environment="PATH=/path/to/wtf/venv/bin"

[Install]
WantedBy=multi-user.target
```

4. Add to pyproject.toml:

```toml
[tool.poetry.scripts]
scheduler = "services.scheduler.__main__:main"
```

5. Create setup script:

```bash
# scripts/setup_scheduler.sh

#!/bin/bash
set -e

echo "Setting up WTF scheduler..."

# Install systemd service
sudo cp scripts/wtf-scheduler.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable wtf-scheduler
sudo systemctl start wtf-scheduler

echo "✅ Scheduler installed and started"
echo "Check status: sudo systemctl status wtf-scheduler"
echo "View logs: sudo journalctl -u wtf-scheduler -f"
```

**Impact:** High - Essential for production

**Estimated Effort:** 4 hours

---

## 🟢 **Medium Priority Issues**

### Issue #8: Missing Notification Integration for Spider/Scraper

**Priority:** 🟢 Medium
**Type:** Missing Feature
**Component:** Notification, Integration

**Problem:**
When spider/scraper find new high-confidence free food events, users are not notified automatically. Events are saved to database but notification service doesn't monitor for new events.

**Current State:**
- Events saved to database
- Notification service exists but doesn't auto-trigger
- No connection between event detection and user notifications

**Solution:**

1. Create event trigger service:

```python
# services/event_notifier/__main__.py

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv(override=True)

from services.supabase_client import get_supabase_client
from services.notification.email_service import send_event_notification

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_new_events(minutes_ago: int = 60) -> List[Dict]:
    """Get events created in the last N minutes."""
    try:
        supabase = get_supabase_client()

        cutoff_time = (datetime.now() - timedelta(minutes=minutes_ago)).isoformat()

        result = supabase.table('events')\
            .select('*')\
            .eq('has_free_food', True)\
            .gte('confidence_score', 0.7)\
            .gte('created_at', cutoff_time)\
            .is_('notified_at', 'null')\
            .execute()

        return result.data
    except Exception as e:
        logger.error(f"Error fetching new events: {e}")
        return []


def get_active_subscribers() -> List[Dict]:
    """Get all active subscribers."""
    try:
        supabase = get_supabase_client()

        result = supabase.table('user_profiles')\
            .select('id, email, preferences')\
            .eq('is_active', True)\
            .eq('email_notifications_enabled', True)\
            .execute()

        return result.data
    except Exception as e:
        logger.error(f"Error fetching subscribers: {e}")
        return []


def mark_event_notified(event_id: int):
    """Mark event as notified."""
    try:
        supabase = get_supabase_client()

        supabase.table('events')\
            .update({'notified_at': datetime.now().isoformat()})\
            .eq('id', event_id)\
            .execute()
    except Exception as e:
        logger.error(f"Error marking event as notified: {e}")


async def send_notifications_for_event(event: Dict, subscribers: List[Dict]):
    """Send notifications to all subscribers for an event."""
    sent_count = 0

    for subscriber in subscribers:
        try:
            # Check user preferences (location, categories, quiet hours, etc.)
            # For now, send to everyone

            await send_event_notification(
                email=subscriber['email'],
                event=event
            )

            sent_count += 1

            # Add small delay to avoid rate limiting
            await asyncio.sleep(0.1)

        except Exception as e:
            logger.error(f"Failed to send notification to {subscriber['email']}: {e}")

    return sent_count


async def process_new_events():
    """Main processing loop."""
    logger.info("Checking for new events to notify...")

    new_events = get_new_events(minutes_ago=60)

    if not new_events:
        logger.info("No new events to notify")
        return

    logger.info(f"Found {len(new_events)} new events to notify")

    subscribers = get_active_subscribers()
    logger.info(f"Sending to {len(subscribers)} active subscribers")

    for event in new_events:
        logger.info(f"Notifying for: {event['title']}")

        sent_count = await send_notifications_for_event(event, subscribers)

        logger.info(f"  ✅ Sent {sent_count} notifications")

        # Mark as notified
        mark_event_notified(event['id'])


def main():
    """Run the event notifier service."""
    logger.info("🔔 Event Notifier Service starting...")

    while True:
        try:
            asyncio.run(process_new_events())
        except Exception as e:
            logger.error(f"Error in notification loop: {e}")

        # Check every 5 minutes
        time.sleep(300)


if __name__ == "__main__":
    main()
```

2. Add to database schema:

```sql
-- Add notified_at column to track when notifications were sent
ALTER TABLE events ADD COLUMN notified_at TIMESTAMP;
CREATE INDEX idx_events_notified_at ON events(notified_at);
```

3. Update docker-compose.yml:

```yaml
  event-notifier:
    build:
      context: .
      dockerfile: services/event_notifier/Dockerfile
    container_name: wtf-event-notifier
    environment:
      - SUPABASE_API_URL=${SUPABASE_API_URL}
      - SUPABASE_SERVICE_ROLE_KEY=${SUPABASE_SERVICE_ROLE_KEY}
      - SMTP_SERVER=${SMTP_SERVER}
      - SMTP_PORT=${SMTP_PORT}
      - SMTP_USER=${SMTP_USER}
      - SMTP_PASSWORD=${SMTP_PASSWORD}
    depends_on:
      - redis
    networks:
      - wtf-network
    restart: unless-stopped
```

**Impact:** High - Core feature for user notifications

**Estimated Effort:** 6 hours

---

### Issue #9: No Event Expiration/Cleanup

**Priority:** 🟢 Medium
**Type:** Missing Feature
**Component:** Database, Maintenance

**Problem:**
Old events accumulate in the database indefinitely. No cleanup process exists for past events.

**Impact:**
- Database grows without bounds
- Performance degrades over time
- Stale events may appear in queries

**Solution:**

1. Create cleanup script:

```python
# scripts/cleanup_old_events.py

import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv(override=True)

from services.supabase_client import get_supabase_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def cleanup_old_events(days_old: int = 90):
    """Archive or delete events older than N days."""
    try:
        supabase = get_supabase_client()

        cutoff_date = (datetime.now() - timedelta(days=days_old)).isoformat()

        logger.info(f"Cleaning up events older than {cutoff_date}...")

        # Option 1: Archive to separate table
        result = supabase.rpc('archive_old_events', {
            'cutoff_date': cutoff_date
        }).execute()

        # Option 2: Soft delete (if you have is_active column)
        # result = supabase.table('events')\
        #     .update({'is_active': False})\
        #     .lt('event_date', cutoff_date)\
        #     .execute()

        # Option 3: Hard delete
        # result = supabase.table('events')\
        #     .delete()\
        #     .lt('event_date', cutoff_date)\
        #     .execute()

        logger.info(f"✅ Cleanup completed")

    except Exception as e:
        logger.error(f"❌ Cleanup failed: {e}")


if __name__ == "__main__":
    cleanup_old_events(days_old=90)
```

2. Add database function for archiving:

```sql
-- supabase/migrations/YYYYMMDDHHMMSS_add_event_archiving.sql

-- Create archive table
CREATE TABLE IF NOT EXISTS events_archive (
    LIKE events INCLUDING ALL
);

-- Create archive function
CREATE OR REPLACE FUNCTION archive_old_events(cutoff_date TIMESTAMP)
RETURNS INTEGER AS $$
DECLARE
    archived_count INTEGER;
BEGIN
    -- Copy old events to archive
    INSERT INTO events_archive
    SELECT * FROM events
    WHERE event_date < cutoff_date;

    GET DIAGNOSTICS archived_count = ROW_COUNT;

    -- Delete from main table
    DELETE FROM events
    WHERE event_date < cutoff_date;

    RETURN archived_count;
END;
$$ LANGUAGE plpgsql;
```

3. Add to scheduler:

```python
# In services/scheduler/__main__.py

schedule.every().sunday.at("02:00").do(cleanup_old_events)
```

**Impact:** Medium - Important for long-term performance

**Estimated Effort:** 3 hours

---

### Issue #10: Missing User Preference Handling

**Priority:** 🟢 Medium
**Type:** Missing Feature
**Component:** Notification, API

**Problem:**
User preferences (categories, locations, quiet hours) are stored in database but not enforced during notification sending.

**Current State:**
- `user_profiles` table has `preferences` JSONB column
- No code reads or enforces these preferences
- All users get all notifications

**Solution:**

1. Create preference filtering:

```python
# services/notification/preference_filter.py

from typing import Dict, List
from datetime import datetime, time
import re


def should_notify_user(user: Dict, event: Dict) -> bool:
    """
    Check if user should be notified about this event based on preferences.

    Args:
        user: User profile with preferences
        event: Event data

    Returns:
        True if user should be notified
    """
    preferences = user.get('preferences', {})

    # Check if notifications are enabled
    if not user.get('email_notifications_enabled', True):
        return False

    # Check quiet hours
    if not check_quiet_hours(preferences):
        return False

    # Check location preferences
    if not check_location_match(preferences, event):
        return False

    # Check category preferences
    if not check_category_match(preferences, event):
        return False

    # Check minimum confidence
    min_confidence = preferences.get('min_confidence', 0.6)
    if event.get('confidence_score', 0) < min_confidence:
        return False

    return True


def check_quiet_hours(preferences: Dict) -> bool:
    """Check if current time is within quiet hours."""
    quiet_hours = preferences.get('quiet_hours', {})

    if not quiet_hours.get('enabled', False):
        return True

    now = datetime.now().time()
    start = time.fromisoformat(quiet_hours.get('start', '22:00'))
    end = time.fromisoformat(quiet_hours.get('end', '08:00'))

    # Handle overnight quiet hours (e.g., 22:00 to 08:00)
    if start > end:
        return not (now >= start or now <= end)
    else:
        return not (start <= now <= end)


def check_location_match(preferences: Dict, event: Dict) -> bool:
    """Check if event location matches user preferences."""
    preferred_locations = preferences.get('locations', [])

    # If no preference set, accept all
    if not preferred_locations:
        return True

    event_location = (event.get('location') or '').lower()

    # Check if any preferred location is in event location
    for loc in preferred_locations:
        if loc.lower() in event_location:
            return True

    return False


def check_category_match(preferences: Dict, event: Dict) -> bool:
    """Check if event category matches user preferences."""
    preferred_categories = preferences.get('categories', [])

    # If no preference set, accept all
    if not preferred_categories:
        return True

    event_title = (event.get('title') or '').lower()
    event_desc = (event.get('description') or '').lower()

    # Simple keyword matching
    # TODO: Improve with proper categorization
    for category in preferred_categories:
        if category.lower() in event_title or category.lower() in event_desc:
            return True

    return False
```

2. Update notification service to use filtering:

```python
# In services/event_notifier/__main__.py

from services.notification.preference_filter import should_notify_user

async def send_notifications_for_event(event: Dict, subscribers: List[Dict]):
    """Send notifications to subscribers based on their preferences."""
    sent_count = 0
    filtered_count = 0

    for subscriber in subscribers:
        try:
            # Check user preferences
            if not should_notify_user(subscriber, event):
                filtered_count += 1
                continue

            await send_event_notification(
                email=subscriber['email'],
                event=event
            )

            sent_count += 1
            await asyncio.sleep(0.1)

        except Exception as e:
            logger.error(f"Failed to send to {subscriber['email']}: {e}")

    logger.info(f"  ✅ Sent {sent_count}, filtered {filtered_count}")
    return sent_count
```

3. Add API endpoints for managing preferences:

```python
# services/subscription_api/routes.py

@app.put("/preferences")
async def update_preferences(
    email: str,
    preferences: Dict
):
    """Update user notification preferences."""
    try:
        supabase = get_supabase_client()

        result = supabase.table('user_profiles')\
            .update({'preferences': preferences})\
            .eq('email', email)\
            .execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="User not found")

        return {
            "message": "Preferences updated successfully",
            "preferences": preferences
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/preferences/{email}")
async def get_preferences(email: str):
    """Get user notification preferences."""
    try:
        supabase = get_supabase_client()

        result = supabase.table('user_profiles')\
            .select('preferences')\
            .eq('email', email)\
            .single()\
            .execute()

        if not result.data:
            raise HTTPException(status_code=404, detail="User not found")

        return result.data.get('preferences', {})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

**Impact:** Medium - Improves user experience

**Estimated Effort:** 5 hours

---

## 🔵 **Low Priority Issues / Enhancements**

### Issue #11: Missing API Authentication

**Priority:** 🔵 Low
**Type:** Security
**Component:** API

**Problem:**
API endpoints are publicly accessible without authentication. Anyone can subscribe/unsubscribe users.

**Security Risks:**
- Spam subscriptions
- Unauthorized data access
- Email bombing attacks

**Solution:**

1. Implement API key authentication:

```python
# services/subscription_api/auth.py

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader
import os

API_KEY_HEADER = APIKeyHeader(name="X-API-Key")


def verify_api_key(api_key: str = Security(API_KEY_HEADER)):
    """Verify API key from request header."""
    valid_api_keys = os.getenv("API_KEYS", "").split(",")

    if api_key not in valid_api_keys:
        raise HTTPException(
            status_code=403,
            detail="Invalid or missing API key"
        )

    return api_key
```

2. Protect endpoints:

```python
# services/subscription_api/main.py

from services.subscription_api.auth import verify_api_key

@app.post("/subscribe")
async def subscribe_user(
    email: str,
    api_key: str = Depends(verify_api_key)
):
    # Endpoint logic...
```

3. Or use Supabase Auth:

```python
from supabase import create_client
from fastapi import Depends, HTTPException

async def get_current_user(token: str = Depends(oauth2_scheme)):
    """Get current authenticated user from Supabase."""
    try:
        user = supabase.auth.get_user(token)
        return user
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid authentication")
```

**Impact:** Medium - Important for production security

**Estimated Effort:** 3 hours

---

### Issue #12: Missing Rate Limiting for Gemini API

**Priority:** 🔵 Low
**Type:** Missing Feature
**Component:** Spider

**Problem:**
Spider doesn't track Gemini API usage or implement rate limiting. Could exceed free tier limits (60 requests/minute).

**Solution:**

```python
# services/spider/rate_limiter.py

import time
from collections import deque
from threading import Lock


class RateLimiter:
    """Rate limiter for API calls."""

    def __init__(self, max_requests: int, time_window: int):
        """
        Args:
            max_requests: Maximum requests allowed in time window
            time_window: Time window in seconds
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = deque()
        self.lock = Lock()

    def acquire(self):
        """Wait if necessary to acquire permission for a request."""
        with self.lock:
            now = time.time()

            # Remove old requests outside time window
            while self.requests and self.requests[0] < now - self.time_window:
                self.requests.popleft()

            # If at limit, wait
            if len(self.requests) >= self.max_requests:
                sleep_time = self.requests[0] + self.time_window - now
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    return self.acquire()

            # Record this request
            self.requests.append(now)


# In spider code:
gemini_limiter = RateLimiter(max_requests=60, time_window=60)

def _gemini_confirm_free_food(...):
    gemini_limiter.acquire()  # Wait if needed
    # Make API call...
```

**Impact:** Low - Only affects heavy usage

**Estimated Effort:** 2 hours

---

### Issue #13: No Error Recovery for Failed Scrapes

**Priority:** 🔵 Low
**Type:** Enhancement
**Component:** Spider, Scraper

**Problem:**
If spider/scraper fails mid-run, there's no mechanism to resume or retry.

**Solution:**

1. Add checkpointing:

```python
# services/spider/checkpoint.py

import json
from pathlib import Path
from typing import Set


class CrawlCheckpoint:
    """Save and resume crawl progress."""

    def __init__(self, checkpoint_file: str):
        self.checkpoint_file = Path(checkpoint_file)
        self.visited_urls: Set[str] = set()
        self.load()

    def load(self):
        """Load checkpoint from disk."""
        if self.checkpoint_file.exists():
            with open(self.checkpoint_file) as f:
                data = json.load(f)
                self.visited_urls = set(data.get('visited_urls', []))

    def save(self):
        """Save checkpoint to disk."""
        with open(self.checkpoint_file, 'w') as f:
            json.dump({
                'visited_urls': list(self.visited_urls),
                'timestamp': datetime.now().isoformat()
            }, f)

    def add_url(self, url: str):
        """Mark URL as visited."""
        self.visited_urls.add(url)
        # Save every 10 URLs
        if len(self.visited_urls) % 10 == 0:
            self.save()

    def is_visited(self, url: str) -> bool:
        """Check if URL was already visited."""
        return url in self.visited_urls

    def clear(self):
        """Clear checkpoint."""
        self.visited_urls.clear()
        if self.checkpoint_file.exists():
            self.checkpoint_file.unlink()
```

2. Use in spider:

```python
checkpoint = CrawlCheckpoint('.crawl_checkpoint.json')

# Check before crawling
if checkpoint.is_visited(url):
    continue

# After successful crawl
checkpoint.add_url(url)

# On completion
checkpoint.clear()
```

**Impact:** Low - Improves resilience

**Estimated Effort:** 2 hours

---

### Issue #14: Missing Integration Tests for Full Pipeline

**Priority:** 🔵 Low
**Type:** Testing
**Component:** Tests

**Problem:**
No end-to-end tests that verify the complete flow: event detection → database → notification.

**Solution:**

```python
# tests/test_e2e_pipeline.py

import pytest
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(override=True)

from services.spider.__main__ import save_event_to_database, FreeFoodEvent
from services.supabase_client import get_supabase_client


@pytest.mark.integration
def test_spider_to_database_pipeline():
    """Test spider can save events to database."""
    # Create test event
    test_event = FreeFoodEvent(
        source_url="https://test.example.com/e2e",
        title="E2E Test Event",
        start=datetime.now().isoformat() + "Z",
        end=None,
        location="Test Location",
        description="End-to-end test",
        proof="Free snacks provided",
        confidence=0.95,
        event_id="e2e_test_001",
        platform="test"
    )

    # Save to database
    event_id = save_event_to_database(test_event)

    assert event_id is not None

    # Verify in database
    supabase = get_supabase_client()
    result = supabase.table('events').select('*').eq('id', event_id).single().execute()

    assert result.data['title'] == "E2E Test Event"
    assert result.data['has_free_food'] == True
    assert result.data['confidence_score'] == 0.95

    # Cleanup
    supabase.table('events').delete().eq('id', event_id).execute()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_notification_pipeline():
    """Test notification sending for new events."""
    # TODO: Implement full notification pipeline test
    pass
```

**Impact:** Low - Improves confidence in deployments

**Estimated Effort:** 4 hours

---

## 📋 **Summary of Issues**

### By Priority:

**Critical (Must Fix):**
- #1: Spider upsert constraint missing
- #2: Scraper not saving to database
- #3: Missing event deduplication

**High Priority:**
- #4: Async test failures
- #5: Linting issues
- #6: Supabase client dotenv issue
- #7: No automated scheduling

**Medium Priority:**
- #8: Missing notification integration
- #9: No event expiration/cleanup
- #10: Missing user preference handling

**Low Priority / Enhancements:**
- #11: Missing API authentication
- #12: Missing rate limiting
- #13: No error recovery
- #14: Missing integration tests
