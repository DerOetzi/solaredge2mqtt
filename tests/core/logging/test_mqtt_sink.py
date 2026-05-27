"""Tests for the MQTT log sink module."""

import json

import pytest

from solaredge2mqtt.core.logging.mqtt_sink import _is_mqtt_related, create_mqtt_log_sink
from solaredge2mqtt.core.mqtt.events import MQTTPublishEvent


def _make_record(name: str) -> dict:
    return {"name": name}


class TestIsMqttRelated:
    """Tests for the _is_mqtt_related filter."""

    def test_aiomqtt_module_is_mqtt_related(self):
        assert _is_mqtt_related(_make_record("aiomqtt.client")) is True

    def test_core_mqtt_module_is_mqtt_related(self):
        assert _is_mqtt_related(_make_record("solaredge2mqtt.core.mqtt")) is True

    def test_core_mqtt_submodule_is_mqtt_related(self):
        assert _is_mqtt_related(_make_record("solaredge2mqtt.core.mqtt.events")) is True

    def test_other_module_not_mqtt_related(self):
        assert _is_mqtt_related(_make_record("solaredge2mqtt.services.modbus")) is False

    def test_empty_name_not_mqtt_related(self):
        assert _is_mqtt_related(_make_record("")) is False

    def test_none_name_not_mqtt_related(self):
        assert _is_mqtt_related({"name": None}) is False


class _FakeRecord:
    """Minimal fake loguru message record."""

    def __init__(self, name: str, level_name: str, message: str, time):
        self.record = {
            "name": name,
            "level": type("Level", (), {"name": level_name})(),
            "message": message,
            "time": time,
        }


class TestCreateMqttLogSink:
    """Tests for create_mqtt_log_sink."""

    @pytest.mark.asyncio
    async def test_publishes_log_record(self, mock_event_bus, sample_timestamp):
        """Non-MQTT log records should be emitted as MQTTPublishEvent."""
        sink = create_mqtt_log_sink(mock_event_bus)
        msg = _FakeRecord("solaredge2mqtt.service", "INFO", "Hello", sample_timestamp)
        await sink(msg)

        mock_event_bus.emit.assert_awaited_once()
        event: MQTTPublishEvent = mock_event_bus.emit.call_args[0][0]
        assert isinstance(event, MQTTPublishEvent)
        assert event.topic == "logging"
        assert event.retain is False

        payload = json.loads(event.payload)
        assert payload["level"] == "INFO"
        assert payload["message"] == "Hello"
        assert payload["module"] == "solaredge2mqtt.service"

    @pytest.mark.asyncio
    async def test_filters_aiomqtt_records(self, mock_event_bus, sample_timestamp):
        """Log records from aiomqtt should NOT be emitted."""
        sink = create_mqtt_log_sink(mock_event_bus)
        msg = _FakeRecord("aiomqtt.client", "ERROR", "MQTT error", sample_timestamp)
        await sink(msg)

        mock_event_bus.emit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_filters_core_mqtt_records(self, mock_event_bus, sample_timestamp):
        """Log records from solaredge2mqtt.core.mqtt should NOT be emitted."""
        sink = create_mqtt_log_sink(mock_event_bus)
        msg = _FakeRecord(
            "solaredge2mqtt.core.mqtt", "WARNING", "broker gone", sample_timestamp
        )
        await sink(msg)

        mock_event_bus.emit.assert_not_awaited()
