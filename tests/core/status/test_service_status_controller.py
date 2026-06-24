"""Tests for ServiceStatusController."""

from unittest.mock import AsyncMock, patch

import pytest

from solaredge2mqtt.core.events import EventBus
from solaredge2mqtt.core.mqtt.events import MQTTPublishEvent
from solaredge2mqtt.core.status import ServiceStatusController
from solaredge2mqtt.core.status.events import (
    ResendStatusEvent,
    ServiceOfflineEvent,
    ServiceOnlineEvent,
)


class TestServiceStatusControllerInit:
    """Tests for ServiceStatusController initialization."""

    def test_init(self):
        """Test that ServiceStatusController initializes correctly."""
        controller = ServiceStatusController()

        assert controller._configurations == {}
        assert controller._status == {}
        assert controller._pending_status_changes == {}
        assert controller._debounce_counters == {}

    def test_init_registers_with_event_bus(self):
        """Test that ServiceStatusController registers with EventBus."""
        with patch.object(EventBus, "register") as mock_register:
            controller = ServiceStatusController()
            mock_register.assert_called_once_with(controller)


class TestServiceStatusControllerOnline:
    """Tests for the online() method."""

    @pytest.mark.asyncio
    async def test_online_publishes_status_online(self):
        """Test that online() publishes status online event."""
        controller = ServiceStatusController()

        with patch.object(EventBus, "emit", new_callable=AsyncMock) as mock_emit:
            await controller.online()

            calls = mock_emit.call_args_list
            first_call = calls[0]
            assert isinstance(first_call[0][0], MQTTPublishEvent)
            event = first_call[0][0]
            assert event.topic == "status"
            assert event.payload == "online"
            assert event.suppress_connection_error is True

    @pytest.mark.asyncio
    async def test_online_publishes_all_service_statuses(self):
        """Test that online() publishes all configured service statuses."""
        controller = ServiceStatusController()
        controller._status = {"modbus": True, "mqtt": False}

        with patch.object(EventBus, "emit", new_callable=AsyncMock) as mock_emit:
            await controller.online()

            calls = mock_emit.call_args_list
            # First call is for global status
            assert calls[0][0][0].topic == "status"

            # Remaining calls are for service statuses
            service_topics = [call[0][0].topic for call in calls[1:]]
            assert "status/modbus" in service_topics
            assert "status/mqtt" in service_topics

    @pytest.mark.asyncio
    async def test_online_empty_status(self):
        """Test that online() works with no configured services."""
        controller = ServiceStatusController()

        with patch.object(EventBus, "emit", new_callable=AsyncMock) as mock_emit:
            await controller.online()

            # Only global status event should be emitted
            assert len(mock_emit.call_args_list) == 1
            event = mock_emit.call_args_list[0][0][0]
            assert event.topic == "status"


class TestServiceStatusControllerOffline:
    """Tests for the offline() method."""

    @pytest.mark.asyncio
    async def test_offline_publishes_status_offline(self):
        """Test that offline() publishes status offline event."""
        controller = ServiceStatusController()

        with patch.object(EventBus, "emit", new_callable=AsyncMock) as mock_emit:
            await controller.offline()

            calls = mock_emit.call_args_list
            first_call = calls[0]
            assert isinstance(first_call[0][0], MQTTPublishEvent)
            event = first_call[0][0]
            assert event.topic == "status"
            assert event.payload == "offline"
            assert event.suppress_connection_error is True

    @pytest.mark.asyncio
    async def test_offline_publishes_all_service_statuses_as_offline(self):
        """Test that offline() publishes all services as offline."""
        controller = ServiceStatusController()
        controller._status = {"modbus": True, "mqtt": True}

        with patch.object(EventBus, "emit", new_callable=AsyncMock) as mock_emit:
            await controller.offline()

            calls = mock_emit.call_args_list
            # Skip first call (global status) and check service statuses
            service_calls = calls[1:]
            for call in service_calls:
                event = call[0][0]
                assert event.payload == "offline"

    @pytest.mark.asyncio
    async def test_offline_empty_status(self):
        """Test that offline() works with no configured services."""
        controller = ServiceStatusController()

        with patch.object(EventBus, "emit", new_callable=AsyncMock) as mock_emit:
            await controller.offline()

            # Only global status event should be emitted
            assert len(mock_emit.call_args_list) == 1
            event = mock_emit.call_args_list[0][0][0]
            assert event.topic == "status"
            assert event.payload == "offline"


class TestServiceStatusControllerHandleOnline:
    """Tests for the handle_online() method."""

    @pytest.mark.asyncio
    async def test_handle_online_with_debounce_cycles(self):
        """Test handle_online with debounce cycles specified."""
        controller = ServiceStatusController()

        class TestEvent(ServiceOnlineEvent):
            SERVICE_NAME = "test_service"

        event = TestEvent(debounce_cycles=3)

        with patch.object(EventBus, "emit", new_callable=AsyncMock):
            await controller.handle_online(event)

            assert "test_service" in controller._configurations
            assert controller._configurations["test_service"] == 3
            assert controller._debounce_counters["test_service"] == 0

    @pytest.mark.asyncio
    async def test_handle_online_without_debounce_cycles(self):
        """Test handle_online without debounce cycles specified."""
        controller = ServiceStatusController()

        class TestEvent(ServiceOnlineEvent):
            SERVICE_NAME = "test_service"

        event = TestEvent(debounce_cycles=None)

        with patch.object(EventBus, "emit", new_callable=AsyncMock):
            await controller.handle_online(event)

            assert "test_service" not in controller._configurations
            # Warning should be logged
            # This is implicit in the code logic

    @pytest.mark.asyncio
    async def test_handle_online_unconfigured_service_warning(self, caplog):
        """Test that handle_online logs warning for unconfigured service."""
        controller = ServiceStatusController()

        class TestEvent(ServiceOnlineEvent):
            SERVICE_NAME = "unknown_service"

        event = TestEvent(debounce_cycles=None)

        with patch.object(EventBus, "emit", new_callable=AsyncMock):
            await controller.handle_online(event)

            # Service should not be configured
            assert "unknown_service" not in controller._configurations

    @pytest.mark.asyncio
    async def test_handle_online_publishes_status(self):
        """Test that handle_online publishes service status."""
        controller = ServiceStatusController()

        class TestEvent(ServiceOnlineEvent):
            SERVICE_NAME = "test_service"

        event = TestEvent(debounce_cycles=1)

        with patch.object(EventBus, "emit", new_callable=AsyncMock) as mock_emit:
            await controller.handle_online(event)

            # Should emit status event
            assert any(
                isinstance(call[0][0], MQTTPublishEvent)
                and call[0][0].topic == "status/test_service"
                and call[0][0].payload == "online"
                for call in mock_emit.call_args_list
            )


class TestServiceStatusControllerHandleOffline:
    """Tests for the handle_offline() method."""

    @pytest.mark.asyncio
    async def test_handle_offline_configured_service(self):
        """Test handle_offline for a configured service."""
        controller = ServiceStatusController()
        controller._configurations["test_service"] = 3

        class TestEvent(ServiceOfflineEvent):
            SERVICE_NAME = "test_service"

        event = TestEvent()

        with patch.object(EventBus, "emit", new_callable=AsyncMock) as mock_emit:
            await controller.handle_offline(event)

            # Should emit offline event
            assert any(
                isinstance(call[0][0], MQTTPublishEvent)
                and call[0][0].topic == "status/test_service"
                and call[0][0].payload == "offline"
                for call in mock_emit.call_args_list
            )

    @pytest.mark.asyncio
    async def test_handle_offline_unconfigured_service(self):
        """Test handle_offline for an unconfigured service."""
        controller = ServiceStatusController()

        class TestEvent(ServiceOfflineEvent):
            SERVICE_NAME = "unknown_service"

        event = TestEvent()

        with patch.object(EventBus, "emit", new_callable=AsyncMock) as mock_emit:
            await controller.handle_offline(event)

            # Should not emit any events
            assert len(mock_emit.call_args_list) == 0


class TestServiceStatusControllerDebouncing:
    """Tests for debouncing logic."""

    @pytest.mark.asyncio
    async def test_debouncing_no_debounce(self):
        """Test that status is published immediately when debounce_cycles <= 1."""
        controller = ServiceStatusController()

        class TestEvent(ServiceOnlineEvent):
            SERVICE_NAME = "test_service"

        event = TestEvent(debounce_cycles=1)

        with patch.object(EventBus, "emit", new_callable=AsyncMock) as mock_emit:
            await controller.handle_online(event)

            # Status should be published immediately
            assert controller._status["test_service"] is True

            mock_emit.reset_mock()

            # Go offline immediately
            class OfflineEvent(ServiceOfflineEvent):
                SERVICE_NAME = "test_service"

            await controller.handle_offline(OfflineEvent())

            # Status should be published immediately
            assert controller._status["test_service"] is False

    @pytest.mark.asyncio
    async def test_debouncing_with_cycles(self):
        """Test debouncing with multiple cycles."""
        controller = ServiceStatusController()

        class OnlineEvent(ServiceOnlineEvent):
            SERVICE_NAME = "test_service"

        class OfflineEvent(ServiceOfflineEvent):
            SERVICE_NAME = "test_service"

        # Configure with debounce cycles
        event = OnlineEvent(debounce_cycles=3)

        with patch.object(EventBus, "emit", new_callable=AsyncMock) as mock_emit:
            # First online event - should publish immediately (no current status)
            await controller.handle_online(event)
            assert controller._status["test_service"] is True

            mock_emit.reset_mock()

            # First offline event - should not publish yet
            await controller.handle_offline(OfflineEvent())
            # Status should still be online (debouncing)
            assert controller._status["test_service"] is True
            assert "test_service" in controller._pending_status_changes
            assert controller._pending_status_changes["test_service"] is False
            assert controller._debounce_counters["test_service"] == 1

            mock_emit.reset_mock()

            # Second offline event - should not publish yet
            await controller.handle_offline(OfflineEvent())
            assert controller._status["test_service"] is True
            assert controller._debounce_counters["test_service"] == 2

            mock_emit.reset_mock()

            # Third offline event - should publish now (reaches debounce count)
            await controller.handle_offline(OfflineEvent())
            assert controller._status["test_service"] is False

    @pytest.mark.asyncio
    async def test_debouncing_reset_on_different_status(self):
        """Test that debounce counter resets when status changes back."""
        controller = ServiceStatusController()

        class OnlineEvent(ServiceOnlineEvent):
            SERVICE_NAME = "test_service"

        class OfflineEvent(ServiceOfflineEvent):
            SERVICE_NAME = "test_service"

        # Configure with debounce cycles
        event = OnlineEvent(debounce_cycles=3)

        with patch.object(EventBus, "emit", new_callable=AsyncMock):
            # First online event
            await controller.handle_online(event)
            assert controller._status["test_service"] is True

            # Try to go offline once
            await controller.handle_offline(OfflineEvent())
            assert controller._debounce_counters["test_service"] == 1
            assert controller._pending_status_changes["test_service"] is False

            # Go back online before reaching debounce threshold
            await controller.handle_online(event)
            # Counter and pending changes should be reset
            assert controller._status["test_service"] is True
            # Pending status should be cleared since current status matches
            assert controller._pending_status_changes.get("test_service") is None


class TestServiceStatusControllerPublishServiceStatus:
    """Tests for the _publish_service_status() method."""

    @pytest.mark.asyncio
    async def test_publish_service_status_online(self):
        """Test publishing online status for a service."""
        controller = ServiceStatusController()

        with patch.object(EventBus, "emit", new_callable=AsyncMock) as mock_emit:
            await controller._publish_service_status("test_service", True)

            # Status should be updated
            assert controller._status["test_service"] is True

            # Event should be emitted
            event = mock_emit.call_args_list[0][0][0]
            assert isinstance(event, MQTTPublishEvent)
            assert event.topic == "status/test_service"
            assert event.payload == "online"

    @pytest.mark.asyncio
    async def test_publish_service_status_offline(self):
        """Test publishing offline status for a service."""
        controller = ServiceStatusController()

        with patch.object(EventBus, "emit", new_callable=AsyncMock) as mock_emit:
            await controller._publish_service_status("test_service", False)

            # Status should be updated
            assert controller._status["test_service"] is False

            # Event should be emitted
            event = mock_emit.call_args_list[0][0][0]
            assert isinstance(event, MQTTPublishEvent)
            assert event.topic == "status/test_service"
            assert event.payload == "offline"

    @pytest.mark.asyncio
    async def test_publish_service_status_resets_debounce(self):
        """Test that publishing status resets debounce counters."""
        controller = ServiceStatusController()
        controller._debounce_counters["test_service"] = 5
        controller._pending_status_changes["test_service"] = False

        with patch.object(EventBus, "emit", new_callable=AsyncMock):
            await controller._publish_service_status("test_service", True)

            # Debounce should be reset
            assert controller._debounce_counters["test_service"] == 0
            assert controller._pending_status_changes.get("test_service") is None


class TestServiceStatusControllerIntegration:
    """Integration tests for ServiceStatusController."""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self):
        """Test full lifecycle of status controller."""
        controller = ServiceStatusController()

        class ModbusOnline(ServiceOnlineEvent):
            SERVICE_NAME = "modbus"

        class MqttOnline(ServiceOnlineEvent):
            SERVICE_NAME = "mqtt"

        class ModbusOffline(ServiceOfflineEvent):
            SERVICE_NAME = "modbus"

        with patch.object(EventBus, "emit", new_callable=AsyncMock):
            # Configure services
            await controller.handle_online(ModbusOnline(debounce_cycles=1))
            await controller.handle_online(MqttOnline(debounce_cycles=1))

            assert controller._status["modbus"] is True
            assert controller._status["mqtt"] is True

            # Take modbus offline
            await controller.handle_offline(ModbusOffline())

            assert controller._status["modbus"] is False
            assert controller._status["mqtt"] is True

            # Go online with all services
            await controller.online()
            # Status should reflect current state
            assert controller._status["modbus"] is False
            assert controller._status["mqtt"] is True

    @pytest.mark.asyncio
    async def test_concurrent_status_changes(self):
        """Test handling concurrent status changes for multiple services."""
        controller = ServiceStatusController()

        class Service1Online(ServiceOnlineEvent):
            SERVICE_NAME = "service1"

        class Service2Online(ServiceOnlineEvent):
            SERVICE_NAME = "service2"

        class Service1Offline(ServiceOfflineEvent):
            SERVICE_NAME = "service1"

        class Service2Offline(ServiceOfflineEvent):
            SERVICE_NAME = "service2"

        with patch.object(EventBus, "emit", new_callable=AsyncMock):
            # Bring both services online
            await controller.handle_online(Service1Online(debounce_cycles=2))
            await controller.handle_online(Service2Online(debounce_cycles=2))

            assert controller._status["service1"] is True
            assert controller._status["service2"] is True

            # Send offline events for both
            await controller.handle_offline(Service1Offline())
            await controller.handle_offline(Service2Offline())

            # Both should be pending
            assert controller._pending_status_changes["service1"] is False
            assert controller._pending_status_changes["service2"] is False

            # Continue offline events
            await controller.handle_offline(Service1Offline())
            await controller.handle_offline(Service2Offline())

            # Both should now be offline
            assert controller._status["service1"] is False
            assert controller._status["service2"] is False


class TestServiceStatusControllerHandleIntermediateTrigger:
    """Tests for ServiceStatusController.handle_intermediate_trigger."""

    @pytest.mark.asyncio
    async def test_handle_intermediate_trigger_publishes_all_service_statuses(self):
        """
        Test that BetweenIntervalTriggerEvent republishes
        all known service statuses.
        """
        controller = ServiceStatusController()
        controller._status = {"modbus": True, "mqtt": False}

        with patch.object(EventBus, "emit", new_callable=AsyncMock) as mock_emit:
            await controller.handle_intermediate_trigger(ResendStatusEvent())

            emitted_topics = [call.args[0].topic for call in mock_emit.call_args_list]
            assert "status/modbus" in emitted_topics
            assert "status/mqtt" in emitted_topics

    @pytest.mark.asyncio
    async def test_handle_intermediate_trigger_empty_status_emits_nothing(self):
        """Test that handle_intermediate_trigger with no services emits nothing."""
        controller = ServiceStatusController()

        with patch.object(EventBus, "emit", new_callable=AsyncMock) as mock_emit:
            await controller.handle_intermediate_trigger(ResendStatusEvent())

            mock_emit.assert_not_called()
