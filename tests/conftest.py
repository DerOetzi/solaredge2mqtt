"""Shared pytest fixtures and configuration for solaredge2mqtt tests."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from solaredge2mqtt.core.events import EventBus


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Schedule slow tests first to reduce xdist stealwork tail latency.

    With ``pytest-xdist --dist=steal``, a small number of long-running tests are
    started immediately, while idle workers keep stealing short tests from busy
    workers. This avoids a late start of slow tests at the end of the run, which
    would otherwise extend total wall-clock time.
    """
    slow = []
    fast = []

    for item in items:
        if "slow" in item.keywords:
            slow.append(item)
        else:
            fast.append(item)

    items[:] = slow + fast


@pytest.fixture
def event_bus():
    """Create an EventBus instance for testing."""
    return EventBus()


@pytest.fixture
def mock_event_bus():
    """Create a mock event bus with mocked emit method."""
    bus = MagicMock()
    bus.emit = AsyncMock()
    bus.subscribe = MagicMock()
    bus.unsubscribe = MagicMock()
    bus.unsubscribe_all = MagicMock()
    return bus


@pytest.fixture
def sample_timestamp():
    """Provide a sample UTC timestamp for testing."""
    return datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def sample_mqtt_settings():
    """Provide sample MQTT settings for testing."""
    return {
        "broker": "localhost",
        "port": 1883,
        "username": "test_user",
        "password": "test_password",
        "client_id": "test_client",
        "topic_prefix": "solaredge",
    }


@pytest.fixture
def sample_influxdb_settings():
    """Provide sample InfluxDB settings for testing."""
    return {
        "host": "localhost",
        "port": 8086,
        "token": "test_token",
        "org": "test_org",
        "bucket": "test_bucket",
    }


@pytest.fixture
def sample_modbus_settings():
    """Provide sample Modbus settings for testing."""
    return {
        "host": "192.168.1.100",  # noqa: S1313
        "port": 1502,
        "unit": 1,
        "timeout": 5,
    }
