"""Tests for StorageControlService."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from solaredge2mqtt.core.mqtt.events import MQTTReceivedEvent, MQTTSubscribeEvent
from solaredge2mqtt.services.modbus.events import ModbusWriteEvent
from solaredge2mqtt.services.modbus.models.inputs import (
    ModbusStorageChargeLimitInput,
    ModbusStorageCommandModeInput,
    ModbusStorageCommandTimeoutInput,
    ModbusStorageDischargeLimitInput,
)
from solaredge2mqtt.services.modbus.storage import StorageControlService
from solaredge2mqtt.services.modbus.sunspec.inverter import (
    SunSpecStorageControlRegister,
)


@pytest.fixture
def mock_service_settings():
    """Create mock service settings."""
    settings = MagicMock()
    settings.modbus.storage_control_enabled = True
    settings.modbus.has_followers = False
    settings.mqtt.topic_prefix = "solaredge"
    return settings


@pytest.fixture
def mock_event_bus():
    """Create mock event bus."""
    event_bus = MagicMock()
    event_bus.emit = AsyncMock()
    event_bus.subscribe = MagicMock()
    return event_bus


class TestStorageControlServiceInit:
    """Tests for StorageControlService initialization."""

    def test_storage_control_service_init(
        self, mock_service_settings, mock_event_bus
    ):
        """Test StorageControlService initialization."""
        service = StorageControlService(mock_service_settings, mock_event_bus)

        assert service.settings == mock_service_settings.modbus
        assert service.mqtt_settings == mock_service_settings.mqtt
        assert service.event_bus == mock_event_bus
        assert service.topic_prefix == "solaredge/modbus/inverter"

    def test_storage_control_service_init_with_followers(
        self, mock_service_settings, mock_event_bus
    ):
        """Test StorageControlService initialization with followers."""
        mock_service_settings.modbus.has_followers = True
        service = StorageControlService(mock_service_settings, mock_event_bus)

        assert service.topic_prefix == "solaredge/modbus/leader/inverter"

    def test_subscribes_to_mqtt_received_event(
        self, mock_service_settings, mock_event_bus
    ):
        """Test that service subscribes to MQTT received events."""
        StorageControlService(mock_service_settings, mock_event_bus)

        mock_event_bus.subscribe.assert_called_once()
        call_args = mock_event_bus.subscribe.call_args
        assert call_args[0][0] == MQTTReceivedEvent


class TestStorageControlServiceAsyncInit:
    """Tests for StorageControlService async initialization."""

    async def test_async_init_subscribes_to_topics(
        self, mock_service_settings, mock_event_bus
    ):
        """Test async_init subscribes to all storage control topics."""
        service = StorageControlService(mock_service_settings, mock_event_bus)
        await service.async_init()

        # Should emit 4 subscribe events
        # (charge_limit, discharge_limit, command_mode, command_timeout)
        assert mock_event_bus.emit.call_count == 4

        # Check that all expected topics are subscribed
        topics = [
            "solaredge/modbus/inverter/storage_control/charge_limit",
            "solaredge/modbus/inverter/storage_control/discharge_limit",
            "solaredge/modbus/inverter/storage_control/command_mode",
            "solaredge/modbus/inverter/storage_control/command_timeout",
        ]

        for call in mock_event_bus.emit.call_args_list:
            event = call[0][0]
            assert isinstance(event, MQTTSubscribeEvent)
            assert event.topic in topics


class TestStorageControlServiceHandleMqttReceived:
    """Tests for handling MQTT received events."""

    async def test_handle_charge_limit_command(
        self, mock_service_settings, mock_event_bus
    ):
        """Test handling charge limit command."""
        service = StorageControlService(mock_service_settings, mock_event_bus)
        input_data = ModbusStorageChargeLimitInput(limit=5000.0)
        event = MQTTReceivedEvent(
            "solaredge/modbus/inverter/storage_control/charge_limit",
            input_data
        )

        await service._handle_mqtt_received_event(event)

        # Should emit write event for charge limit
        mock_event_bus.emit.assert_called_once()
        write_event = mock_event_bus.emit.call_args[0][0]
        assert isinstance(write_event, ModbusWriteEvent)
        assert write_event.register == SunSpecStorageControlRegister.CHARGE_LIMIT
        assert write_event.payload == 5000.0

    async def test_handle_discharge_limit_command(
        self, mock_service_settings, mock_event_bus
    ):
        """Test handling discharge limit command."""
        service = StorageControlService(mock_service_settings, mock_event_bus)
        input_data = ModbusStorageDischargeLimitInput(limit=8000.0)
        event = MQTTReceivedEvent(
            "solaredge/modbus/inverter/storage_control/discharge_limit",
            input_data
        )

        await service._handle_mqtt_received_event(event)

        # Should emit write event for discharge limit
        mock_event_bus.emit.assert_called_once()
        write_event = mock_event_bus.emit.call_args[0][0]
        assert isinstance(write_event, ModbusWriteEvent)
        assert write_event.register == SunSpecStorageControlRegister.DISCHARGE_LIMIT
        assert write_event.payload == 8000.0

    async def test_handle_command_mode_command(
        self, mock_service_settings, mock_event_bus
    ):
        """Test handling command mode command."""
        service = StorageControlService(mock_service_settings, mock_event_bus)
        input_data = ModbusStorageCommandModeInput(mode=5)
        event = MQTTReceivedEvent(
            "solaredge/modbus/inverter/storage_control/command_mode",
            input_data
        )

        await service._handle_mqtt_received_event(event)

        # Should emit write event for command mode
        mock_event_bus.emit.assert_called_once()
        write_event = mock_event_bus.emit.call_args[0][0]
        assert isinstance(write_event, ModbusWriteEvent)
        assert write_event.register == SunSpecStorageControlRegister.COMMAND_MODE
        assert write_event.payload == 5

    async def test_handle_command_timeout_command(
        self, mock_service_settings, mock_event_bus
    ):
        """Test handling command timeout command."""
        service = StorageControlService(mock_service_settings, mock_event_bus)
        input_data = ModbusStorageCommandTimeoutInput(timeout=3600)
        event = MQTTReceivedEvent(
            "solaredge/modbus/inverter/storage_control/command_timeout",
            input_data
        )

        await service._handle_mqtt_received_event(event)

        # Should emit write event for command timeout
        mock_event_bus.emit.assert_called_once()
        write_event = mock_event_bus.emit.call_args[0][0]
        assert isinstance(write_event, ModbusWriteEvent)
        assert write_event.register == SunSpecStorageControlRegister.COMMAND_TIMEOUT
        assert write_event.payload == 3600

    async def test_ignores_non_storage_control_topics(
        self, mock_service_settings, mock_event_bus
    ):
        """Test that non-storage control topics are ignored."""
        service = StorageControlService(mock_service_settings, mock_event_bus)
        input_data = MagicMock()
        event = MQTTReceivedEvent(
            "solaredge/modbus/inverter/other_topic",
            input_data
        )

        await service._handle_mqtt_received_event(event)

        # Should not emit any events
        mock_event_bus.emit.assert_not_called()
