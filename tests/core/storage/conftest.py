"""Fixtures for the storage tests, all running against a real database file."""

from datetime import datetime, timezone

import pytest

from solaredge2mqtt.core.storage import Point, StorageService
from solaredge2mqtt.core.storage.settings import StorageSettings
from solaredge2mqtt.services.energy.settings import PriceSettings

HOUR = datetime(2026, 8, 19, 11, 0, tzinfo=timezone.utc)


@pytest.fixture
def storage_settings():
    """Provide storage settings with the defaults used in production."""
    return StorageSettings()


@pytest.fixture
def prices():
    """Provide configured prices so the money fields are derived."""
    return PriceSettings(consumption=0.30, delivery=0.08, currency="EUR")


@pytest.fixture
async def storage(tmp_path, storage_settings, prices):
    """Provide an initialized storage service on a temporary database."""
    service = StorageService(storage_settings, prices, config_dir=str(tmp_path))
    await service.async_init()
    yield service
    await service.close()


@pytest.fixture
def hour():
    """Provide the full UTC hour the seeded samples belong to."""
    return HOUR


@pytest.fixture
def seed(storage):
    """Provide a helper writing (timestamp, value) samples of one field."""

    async def _seed(measurement, field, tags, samples):
        points = []
        for moment, value in samples:
            point = Point(measurement).time(moment)
            for tag_key, tag_value in tags.items():
                point.tag(tag_key, tag_value)
            point.field(field, value)
            points.append(point)

        await storage.write_points(points)

    return _seed
