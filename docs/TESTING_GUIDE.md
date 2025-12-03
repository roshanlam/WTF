# Testing Guide

## Quick Start

**Always activate the virtual environment before running tests:**

```bash
source venv/bin/activate
```

---

## Running Tests

### Method 1: Using Make (Recommended)
```bash
make test                    # Run all tests
make test-cov               # Run with coverage report
```

### Method 2: Using Poetry
```bash
poetry run pytest                                    # Run all tests
poetry run pytest tests/                             # Run all tests in tests/ directory
poetry run pytest --cov=services --cov-report=term   # Run with coverage
```

### Method 3: Direct pytest (after activating venv)
```bash
source venv/bin/activate

# Run all tests
pytest

# Run all tests with verbose output
pytest -v

# Run all tests with coverage
pytest --cov=services --cov-report=term-missing
```

---

## Common Test Commands

### Run All Tests
```bash
source venv/bin/activate
pytest                           # All tests, concise output
pytest -v                        # All tests, verbose output
pytest -vv                       # All tests, very verbose output
```

### Run Specific Test Files
```bash
source venv/bin/activate

# Run tests for a specific service
pytest tests/test_mq.py -v
pytest tests/test_mq_consumer.py -v
pytest tests/test_api.py -v                    # Example: API service tests
pytest tests/test_notification.py -v           # Example: Notification service tests

# Run multiple specific test files
pytest tests/test_mq.py tests/test_mq_consumer.py -v
```

### Run Specific Test Functions
```bash
source venv/bin/activate

# Run a specific test function
pytest tests/test_mq.py::test_message_queue_publish -v

# Run all tests matching a pattern
pytest -k "publish" -v                         # All tests with "publish" in the name
pytest -k "consumer and not exception" -v      # Tests matching pattern
```

---

## Coverage Testing

### Run with Coverage for All Services
```bash
source venv/bin/activate

# Coverage for all services
pytest --cov=services --cov-report=term-missing

# Coverage for all services with HTML report
pytest --cov=services --cov-report=html
open htmlcov/index.html
```

### Coverage for Specific Services
```bash
source venv/bin/activate

# Message queue coverage
pytest tests/test_mq.py tests/test_mq_consumer.py \
  --cov=services.mq --cov=services.mq_consumer \
  --cov-report=term-missing

# API service coverage
pytest tests/test_api.py \
  --cov=services.api \
  --cov-report=term-missing

# Notification service coverage
pytest tests/test_notification.py \
  --cov=services.notification \
  --cov-report=term-missing

# Multiple services coverage
pytest tests/test_api.py tests/test_decision_gateway.py \
  --cov=services.api --cov=services.decision_gateway \
  --cov-report=term-missing
```

### Enforce Minimum Coverage
```bash
source venv/bin/activate

# Fail if coverage is below 95%
pytest --cov=services --cov-fail-under=95

# Fail if coverage is below 90% for specific service
pytest tests/test_mq.py \
  --cov=services.mq \
  --cov-fail-under=90
```

---

## Useful Test Options

### Control Test Output
```bash
source venv/bin/activate

pytest -q                        # Quiet mode (minimal output)
pytest -v                        # Verbose mode
pytest -vv                       # Very verbose mode
pytest -s                        # Show print statements
pytest --tb=short                # Short traceback format
pytest --tb=line                 # One-line traceback format
pytest --tb=no                   # No traceback
```

### Control Test Execution
```bash
source venv/bin/activate

pytest -x                        # Stop on first failure
pytest --maxfail=3               # Stop after 3 failures
pytest --lf                      # Run last failed tests only
pytest --ff                      # Run failed tests first, then others
pytest -n auto                   # Run tests in parallel (requires pytest-xdist)
```

### Show Test Duration
```bash
source venv/bin/activate

pytest --durations=10            # Show 10 slowest tests
pytest --durations=0             # Show all test durations
```

---

## Writing Tests

### Test File Structure

Create test files in the `tests/` directory following this naming convention:

```
tests/
├── test_<service_name>.py       # Tests for a service
├── test_<module_name>.py        # Tests for a module
├── conftest.py                  # Shared fixtures
└── __init__.py
```

**Example**: For `services/notification/__main__.py`, create `tests/test_notification.py`

### Basic Test Template

```python
"""Tests for <service/module name>."""

import pytest
from services.<service_name> import <function_or_class>


@pytest.fixture
def sample_data():
    """Create sample data for testing."""
    return {
        "key": "value"
    }


def test_basic_functionality(sample_data):
    """Test basic functionality."""
    # Arrange
    expected = "expected_value"

    # Act
    result = some_function(sample_data)

    # Assert
    assert result == expected


def test_error_handling():
    """Test error handling."""
    with pytest.raises(ValueError):
        some_function_that_raises_error()


class TestClassName:
    """Test class for grouping related tests."""

    def test_method_one(self):
        """Test method description."""
        assert True

    def test_method_two(self):
        """Test method description."""
        assert True
```

### Fixtures in conftest.py

Share fixtures across test files using `tests/conftest.py`:

```python
"""Shared test fixtures."""

import pytest
from models import FreeFoodEvent
from datetime import datetime, timezone
from uuid import uuid4


@pytest.fixture
def sample_event():
    """Create a sample FreeFoodEvent for testing."""
    return FreeFoodEvent(
        event_id=str(uuid4()),
        title="Test Event",
        source="test",
        published_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_redis(monkeypatch):
    """Mock Redis client for testing."""
    # Your mock implementation
    pass
```

### Test Coverage Best Practices

1. **Aim for 95%+ coverage** for all services
2. **Test happy paths** - Normal, expected behavior
3. **Test error paths** - Exception handling, invalid inputs
4. **Test edge cases** - Boundary conditions, empty inputs, None values
5. **Test integration** - Service interactions, end-to-end flows

### Example: Testing a New Service

```python
# tests/test_notification.py
"""Tests for Notification Service."""

import pytest
from services.notification.__main__ import NotificationService


@pytest.fixture
def notification_service():
    """Create NotificationService instance."""
    return NotificationService()


def test_notification_service_initialization(notification_service):
    """Test that NotificationService initializes correctly."""
    assert notification_service is not None
    assert notification_service.channels is not None


def test_send_notification_success(notification_service, sample_event):
    """Test sending notification successfully."""
    result = notification_service.notify(sample_event)
    assert result is True


def test_send_notification_with_no_subscribers(notification_service, sample_event):
    """Test notification when there are no subscribers."""
    # Mock empty subscriber list
    notification_service._get_subscribers = lambda x: []
    result = notification_service.notify(sample_event)
    # Verify behavior with no subscribers
```

---

## Test Directory Structure

```
tests/
├── __init__.py
├── conftest.py                  # Shared fixtures
├── test_config.py               # Configuration tests
├── test_mq.py                   # Message queue tests
├── test_mq_consumer.py          # MQ Consumer service tests
├── test_api.py                  # API service tests (to be added)
├── test_decision_gateway.py     # Decision Gateway tests (to be added)
├── test_llm_agent.py            # LLM Agent tests (to be added)
├── test_notification.py         # Notification service tests (to be added)
└── integration/                 # Integration tests (optional)
    └── test_end_to_end.py
```

---

## Troubleshooting

### Error: "cannot import name 'FixtureDef' from 'pytest'"

**Problem**: You're using the global pytest installation instead of the venv.

**Solution**: Always activate the venv first:
```bash
source venv/bin/activate
```

**Why this happens**: The global Python installation may have incompatible versions of pytest and pytest-asyncio.

### Check which pytest you're using
```bash
which pytest
# Should output: /path/to/wtf/venv/bin/pytest

# If it shows /usr/local/bin/pytest or similar, activate venv first
source venv/bin/activate
which pytest
```

### Verify venv is activated
Your prompt should show `(venv)` at the beginning:
```bash
(venv) user@machine:~/wtf$
```

If not, activate it:
```bash
source venv/bin/activate
```

---

## Test Coverage Requirements

### Project Standards
- **Minimum Coverage**: 95% for all services
- **Target**: 100% coverage
- **Coverage Tools**: pytest-cov

### Current Coverage Status

| Service | Coverage | Status |
|---------|----------|--------|
| Message Queue (`services/mq.py`) | 100% | ✅ |
| MQ Consumer (`services/mq_consumer/__main__.py`) | 100% | ✅ |
| API Service | TBD | 🔄 |
| Decision Gateway | TBD | 🔄 |
| LLM Agent | TBD | 🔄 |
| Notification Service | TBD | 🔄 |

### Checking Coverage for a Service

```bash
source venv/bin/activate

# Check coverage for a specific service
pytest tests/test_<service>.py --cov=services.<service> --cov-report=term-missing

# Example: Check API service coverage
pytest tests/test_api.py --cov=services.api --cov-report=term-missing
```

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install poetry
          poetry install

      - name: Run tests with coverage
        run: |
          poetry run pytest --cov=services --cov-fail-under=95 --cov-report=term-missing

      - name: Upload coverage reports
        uses: codecov/codecov-action@v3
        if: always()
```
---

## Quick Reference

### Most Common Commands

```bash
# Activate environment
source venv/bin/activate

# Run all tests
pytest

# Run tests with coverage
pytest --cov=services --cov-report=term-missing

# Run specific test file
pytest tests/test_mq.py -v

# Run specific test function
pytest tests/test_mq.py::test_message_queue_publish -v

# Run tests matching pattern
pytest -k "notification" -v

# Stop on first failure
pytest -x

# Show print statements
pytest -s
```
---

## Testing Checklist

When adding a new service or feature:

- [ ] Create test file: `tests/test_<service_name>.py`
- [ ] Write tests for happy path (normal operation)
- [ ] Write tests for error handling
- [ ] Write tests for edge cases
- [ ] Achieve 95%+ code coverage
- [ ] All tests pass locally
- [ ] Add fixtures to `conftest.py` if reusable
- [ ] Update this guide if new patterns emerge
- [ ] Run `make test-cov` to verify coverage

---

## Additional Resources

### Documentation
- `TEST_COVERAGE_REPORT.md` - Detailed coverage analysis for message queue
- `README.md` - Project setup instructions
- `docs/messaging.md` - Message queue documentation
- `docs/architecture.md` - System architecture

### Pytest Documentation
- [Pytest Official Docs](https://docs.pytest.org/)
- [Pytest Fixtures](https://docs.pytest.org/en/stable/fixture.html)
- [Pytest Parametrize](https://docs.pytest.org/en/stable/parametrize.html)
- [Pytest Coverage](https://pytest-cov.readthedocs.io/)

### Testing Best Practices
- Use descriptive test names
- One assertion per test (when possible)
- Follow Arrange-Act-Assert pattern
- Mock external dependencies
- Keep tests fast and isolated
- Don't test third-party libraries
