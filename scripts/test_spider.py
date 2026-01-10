#!/usr/bin/env python3
"""
Test script for the improved spider.

Usage:
    python scripts/test_spider.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def test_keyword_detection():
    """Test improved keyword detection."""
    from services.spider.__main__ import _keyword_might_have_free_food

    test_cases = [
        ("Join us for free pizza!", True),
        ("Pizza will be provided", True),
        ("Free food for all attendees", True),
        ("Refreshments provided", True),
        ("Tacos and boba available", True),
        ("Cookies and coffee served", True),
        ("Bring your own food", False),
        ("No food provided", False),
        ("Food not available", False),  # Negation detected
        ("Regular meeting", False),
        ("Complimentary food served", True),  # Additional test
        ("Free lunch for attendees", True),  # Additional test
    ]

    print("=" * 60)
    print("Testing Keyword Detection")
    print("=" * 60)

    passed = 0
    failed = 0

    for text, expected in test_cases:
        result = _keyword_might_have_free_food(text)
        status = "✅" if result == expected else "❌"
        if result == expected:
            passed += 1
        else:
            failed += 1

        print(f"{status} '{text}' -> {result} (expected {expected})")

    print(f"\nResults: {passed}/{len(test_cases)} passed")
    return failed == 0


def test_date_parsing():
    """Test improved date parsing."""
    from services.spider.__main__ import _try_parse_dt

    test_dates = [
        "2025-01-15T15:00:00Z",
        "2025-01-15 15:00:00",
        "01/15/2025 3:00 PM",
        "01/15/2025",
        "January 15, 2025 3:00 PM",
        "Jan 15, 2025",
        "Monday, January 15, 2025",
    ]

    print("\n" + "=" * 60)
    print("Testing Date Parsing")
    print("=" * 60)

    passed = 0
    failed = 0

    for date_str in test_dates:
        result = _try_parse_dt(date_str)
        status = "✅" if result else "❌"
        if result:
            passed += 1
            print(f"{status} '{date_str}' -> {result.strftime('%Y-%m-%d %H:%M')}")
        else:
            failed += 1
            print(f"{status} '{date_str}' -> FAILED")

    print(f"\nResults: {passed}/{len(test_dates)} passed")
    return failed == 0


def test_platform_detection():
    """Test platform detection."""
    from services.spider.__main__ import _detect_platform

    test_cases = [
        ("https://events.localist.com/...", "<html>...</html>", "localist"),
        ("https://www.eventbrite.com/e/...", "<html>...</html>", "eventbrite"),
        ("https://www.facebook.com/events/...", "<html>...</html>", "facebook"),
        (
            "https://example.com/event",
            '<script type="application/ld+json">{"@type":"Event"}</script>',
            "schema.org",
        ),
        ("https://example.com/page", "<html>...</html>", "custom"),
    ]

    print("\n" + "=" * 60)
    print("Testing Platform Detection")
    print("=" * 60)

    passed = 0
    failed = 0

    for url, html, expected in test_cases:
        result = _detect_platform(url, html)
        status = "✅" if result == expected else "❌"
        if result == expected:
            passed += 1
        else:
            failed += 1

        print(f"{status} {url} -> {result} (expected {expected})")

    print(f"\nResults: {passed}/{len(test_cases)} passed")
    return failed == 0


def test_url_prioritization():
    """Test URL prioritization."""
    from services.spider.__main__ import _is_likely_event_page

    test_cases = [
        ("https://example.com/events/free-pizza", True),
        ("https://example.com/calendar/january", True),
        ("https://events.localist.com/umass/event/...", True),
        ("https://www.eventbrite.com/e/...", True),
        ("https://example.com/about", False),
        ("https://example.com/contact", False),
        ("https://example.com/home", False),
    ]

    print("\n" + "=" * 60)
    print("Testing URL Prioritization")
    print("=" * 60)

    passed = 0
    failed = 0

    for url, expected in test_cases:
        result = _is_likely_event_page(url)
        status = "✅" if result == expected else "❌"
        if result == expected:
            passed += 1
        else:
            failed += 1

        print(f"{status} {url} -> {result} (expected {expected})")

    print(f"\nResults: {passed}/{len(test_cases)} passed")
    return failed == 0


def main():
    print("\n" + "=" * 60)
    print("WTF Spider Test Suite")
    print("=" * 60 + "\n")

    results = []

    # Run all tests
    results.append(("Keyword Detection", test_keyword_detection()))
    results.append(("Date Parsing", test_date_parsing()))
    results.append(("Platform Detection", test_platform_detection()))
    results.append(("URL Prioritization", test_url_prioritization()))

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    all_passed = True
    for name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status} - {name}")
        if not passed:
            all_passed = False

    print("=" * 60)

    if all_passed:
        print("\n🎉 All tests passed! Spider is ready.")
        return 0
    else:
        print("\n❌ Some tests failed. Please check the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
