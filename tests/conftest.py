"""Pytest configuration and fixtures."""

import pytest


@pytest.fixture
def sample_event():
    """Sample event payload for testing."""
    return {
        "event_type": "free-food",
        "location": "CS Building Room 140",
        "timestamp": "2025-10-30T12:00:00Z",
    }
