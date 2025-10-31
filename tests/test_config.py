"""Tests for configuration module."""

from services import config


def test_config_loads_env_variables():
    """Test that config loads environment variables."""
    assert config.REDIS_URL is not None
    assert config.MQ_STREAM is not None


def test_redis_url_format():
    """Test that REDIS_URL has correct format."""
    assert config.REDIS_URL.startswith("redis://")


def test_mq_stream_not_empty():
    """Test that MQ_STREAM is not empty."""
    assert len(config.MQ_STREAM) > 0
