#!/usr/bin/env python3
"""
Spider Setup Script

This script helps set up the spider service by:
1. Checking all required environment variables
2. Testing Supabase connection
3. Testing Gemini API connection
4. Creating the spider event source in the database
5. Running a quick test crawl

Usage:
    python scripts/setup_spider.py
    python scripts/setup_spider.py --check-only
    python scripts/setup_spider.py --test-crawl
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def check_env_vars() -> bool:
    """Check if all required environment variables are set."""
    required_vars = {
        "GEMINI_API_KEY": "Get from https://aistudio.google.com/app/apikey",
        "SUPABASE_URL": "Get from Supabase Dashboard → Settings → API",
        "SUPABASE_SERVICE_ROLE_KEY": "Get from Supabase Dashboard → Settings → API",
    }

    optional_vars = {
        "SPIDER_SEED_URLS": "https://events.umass.edu",
        "SPIDER_MAX_PAGES": "300",
        "SPIDER_MAX_DEPTH": "3",
        "SPIDER_CONCURRENT_REQUESTS": "10",
        "SPIDER_MIN_CONFIDENCE": "0.60",
        "SPIDER_DAYS_LOOKAHEAD": "90",
        "GEMINI_MODEL": "gemini-2.0-flash",
    }

    print("\n" + "=" * 60)
    print("🔍 Checking Environment Variables")
    print("=" * 60)

    all_set = True
    for var, help_text in required_vars.items():
        value = os.getenv(var)
        if value:
            # Mask sensitive values
            masked = value[:8] + "..." if len(value) > 12 else "***"
            print(f"✅ {var}: {masked}")
        else:
            print(f"❌ {var}: NOT SET")
            print(f"   ℹ️  {help_text}")
            all_set = False

    print("\n📋 Optional Variables (with defaults):")
    for var, default in optional_vars.items():
        value = os.getenv(var, default)
        print(f"   {var}: {value}")

    return all_set


def test_supabase_connection() -> bool:
    """Test Supabase database connection."""
    print("\n" + "=" * 60)
    print("🔌 Testing Supabase Connection")
    print("=" * 60)

    try:
        from services.supabase_client import get_supabase_client

        supabase = get_supabase_client()

        # Test query
        response = supabase.table("event_sources").select("id, name").limit(5).execute()

        print("✅ Successfully connected to Supabase")
        print(f"   Event sources in database: {len(response.data)}")

        for source in response.data:
            print(f"   - {source['name']} (id: {source['id']})")

        return True

    except Exception as e:
        print(f"❌ Failed to connect to Supabase: {e}")
        return False


def test_gemini_connection() -> bool:
    """Test Gemini API connection."""
    print("\n" + "=" * 60)
    print("🤖 Testing Gemini API Connection")
    print("=" * 60)

    try:
        from google import genai
        from google.genai.types import GenerateContentConfig

        api_key = os.getenv("GEMINI_API_KEY")
        model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

        if not api_key:
            print("❌ GEMINI_API_KEY not set")
            return False

        client = genai.Client(api_key=api_key)

        # Simple test query
        response = client.models.generate_content(
            model=model,
            contents=["Say 'Hello, WTF Spider!' in exactly those words"],
            config=GenerateContentConfig(temperature=0.0),
        )

        print("✅ Gemini API connected successfully")
        print(f"   Model: {model}")
        print(f"   Response: {response.text[:50]}...")

        return True

    except Exception as e:
        print(f"❌ Failed to connect to Gemini: {e}")
        return False


def setup_spider_source() -> bool:
    """Create or update the spider event source in the database."""
    print("\n" + "=" * 60)
    print("🕷️ Setting Up Spider Event Source")
    print("=" * 60)

    try:
        from services.supabase_client import get_supabase_client

        supabase = get_supabase_client()

        # Check if spider source exists
        response = (
            supabase.table("event_sources")
            .select("id, name")
            .eq("name", "WTF Spider")
            .execute()
        )

        if response.data:
            source_id = response.data[0]["id"]
            print(f"✅ Spider source already exists (id: {source_id})")
            return True

        # Create spider source
        source_data = {
            "name": "WTF Spider",
            "type": "api",
            "source_identifier": "wtf-spider-v2",
            "is_active": True,
            "is_verified": True,
            "trust_score": 80,
            "priority": 10,
            "description": "Automated web crawler for detecting free food events",
            "config": {
                "version": "2.0",
                "platforms": [
                    "localist",
                    "eventbrite",
                    "facebook",
                    "meetup",
                    "schema.org",
                ],
            },
        }

        response = supabase.table("event_sources").insert(source_data).execute()

        if response.data:
            source_id = response.data[0]["id"]
            print(f"✅ Created spider event source (id: {source_id})")
            return True

        print("❌ Failed to create spider source")
        return False

    except Exception as e:
        print(f"❌ Error setting up spider source: {e}")
        return False


def run_test_crawl() -> bool:
    """Run a quick test crawl to verify everything works."""
    print("\n" + "=" * 60)
    print("🧪 Running Test Crawl")
    print("=" * 60)

    try:
        from services.spider.__main__ import (
            crawl_confirmed_free_food_events,
            DEFAULT_SEED_URLS,
        )

        seed_url = (
            DEFAULT_SEED_URLS[0] if DEFAULT_SEED_URLS else "https://events.umass.edu"
        )

        print(f"   Seed URL: {seed_url}")
        print("   Max Pages: 10 (test mode)")
        print("   Max Depth: 1 (test mode)")
        print("")

        events = crawl_confirmed_free_food_events(
            seed_url=seed_url,
            max_pages=10,
            max_depth=1,
            save_to_db=True,
        )

        print("\n✅ Test crawl completed!")
        print(f"   Events found: {len(events)}")

        if events:
            print("\n   Sample event:")
            event = events[0]
            print(f"   - Title: {event['title'][:50]}...")
            print(f"   - Location: {event['location']}")
            print(f"   - When: {event['start']}")
            print(f"   - Confidence: {event['confidence']}")

        return True

    except Exception as e:
        print(f"❌ Test crawl failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def print_next_steps():
    """Print next steps for the user."""
    print("\n" + "=" * 60)
    print("📋 Next Steps")
    print("=" * 60)
    print("""
1. Run the spider:
   make run-spider                    # Use default URLs
   make run-spider-url URL=https://... # Use specific URL

2. Check the database for events:
   psql $SUPABASE_DB_URL -c "SELECT COUNT(*) FROM events WHERE has_free_food = TRUE;"

3. View crawl results:
   cat free_food_events.json

4. Run in production:
   - Set up a cron job or scheduled task
   - Use: poetry run spider --all-defaults

5. Monitor:
   - Check logs for errors
   - Monitor Gemini API usage
""")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Set up the WTF Spider")
    parser.add_argument(
        "--check-only", action="store_true", help="Only check configuration"
    )
    parser.add_argument("--test-crawl", action="store_true", help="Run a test crawl")
    args = parser.parse_args()

    print("\n" + "=" * 60)
    print("🕷️  WTF Spider Setup")
    print("=" * 60)

    # Check environment variables
    env_ok = check_env_vars()

    if not env_ok:
        print("\n❌ Please set all required environment variables first.")
        print("   Copy .env.example to .env and fill in the values.")
        sys.exit(1)

    if args.check_only:
        print("\n✅ Configuration check complete!")
        sys.exit(0)

    # Test connections
    supabase_ok = test_supabase_connection()
    gemini_ok = test_gemini_connection()

    if not supabase_ok or not gemini_ok:
        print("\n❌ Please fix the connection issues above.")
        sys.exit(1)

    # Set up spider source
    source_ok = setup_spider_source()

    if not source_ok:
        print("\n⚠️  Spider source setup had issues, but continuing...")

    # Run test crawl if requested
    if args.test_crawl:
        crawl_ok = run_test_crawl()
        if not crawl_ok:
            print("\n⚠️  Test crawl had issues.")

    print_next_steps()

    print("\n" + "=" * 60)
    print("✅ Spider Setup Complete!")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
