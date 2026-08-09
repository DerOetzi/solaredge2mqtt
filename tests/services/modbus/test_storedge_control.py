"""Tests for the storedge_control module."""

from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from solaredge2mqtt.services.modbus.models.inverter import ModbusStorEdgeControl
from solaredge2mqtt.services.modbus.storedge_control import StorEdgeControl
from solaredge2mqtt.services.modbus.storedge_control_events import (
    StoredgeAcChargeLimitEvent,
    StoredgeAcChargePolicyEvent,
    StoredgeBackupReservedSettingEvent,
    StoredgeControlModeEvent,
    StoredgeDefaultModeEvent,
    StoredgeRemoteControlChargeLimitEvent,
    StoredgeRemoteControlCommandModeEvent,
    StoredgeRemoteControlCommandTimeoutEvent,
    StoredgeRemoteControlDischargeLimitEvent,
)
from solaredge2mqtt.services.modbus.storedge_control_inputs import (
    StoredgeAcChargeLimitInput,
    StoredgeAcChargePolicyInput,
    StoredgeBackupReservedSettingInput,
    StoredgeControlModeInput,
    StoredgeDefaultModeInput,
    StoredgeRemoteControlChargeLimitInput,
    StoredgeRemoteControlCommandModeInput,
    StoredgeRemoteControlCommandTimeoutInput,
    StoredgeRemoteControlDischargeLimitInput,
)
from solaredge2mqtt.services.modbus.sunspec.inverter import (
    SunSpecStorEdgeControlRegister,
)


def make_last_known(**overrides) -> ModbusStorEdgeControl:
    """Build a ModbusStorEdgeControl to seed StorEdgeControl._last_known in tests."""
    defaults = {
        "storage_control_mode": 4,
        "storage_ac_charge_policy": 1,
        "storage_ac_charge_limit": 0.0,
        "storage_backup_reserved_setting": 10.0,
        "storage_default_mode": 6,
        "remote_control_command_timeout": 1800,
        "remote_control_command_mode": 6,
        "remote_control_charge_limit": 4000.0,
        "remote_control_discharge_limit": 4000.0,
    }
    defaults.update(overrides)
    return ModbusStorEdgeControl(**defaults)


@pytest.fixture
def mock_service_settings():
    """Create mock service settings."""
    settings = MagicMock()
    settings.modbus = MagicMock()
    settings.modbus.has_followers = False
    settings.modbus.storedge_control_enabled = True
    settings.mqtt = MagicMock()
    settings.mqtt.topic_prefix = "solaredge"
    return settings


class TestStorEdgeControlInit:
    """Tests for StorEdgeControl initialization."""

    def test_topic_prefix_without_followers(
        self, mock_service_settings, mock_event_bus
    ):
        """Test topic_prefix omits unit key when there are no followers."""
        control = StorEdgeControl(mock_service_settings)

        assert control.topic_prefix == "modbus/inverter/storedge_control"

    def test_topic_prefix_with_followers(self, mock_service_settings, mock_event_bus):
        """Test topic_prefix includes the leader unit key when followers exist."""
        mock_service_settings.modbus.has_followers = True

        control = StorEdgeControl(mock_service_settings)

        assert control.topic_prefix == "modbus/leader/inverter/storedge_control"

    def test_init_registers_with_event_bus(self, mock_service_settings, mock_event_bus):
        """Test the instance registers itself with the EventBus."""
        control = StorEdgeControl(mock_service_settings)

        mock_event_bus.register.assert_called_once_with(control)


class TestStorEdgeControlAsyncInit:
    """Tests for StorEdgeControl.async_init."""

    @pytest.mark.asyncio
    async def test_async_init_subscribes_all_topics_when_enabled(
        self, mock_service_settings, mock_event_bus
    ):
        """Test async_init subscribes to all nine writable field topics."""
        control = StorEdgeControl(mock_service_settings)

        await control.async_init()

        emitted = [c[0][0] for c in mock_event_bus.emit.call_args_list]
        topics = {event.topic for event in emitted}

        assert topics == {
            "modbus/inverter/storedge_control/storage_control_mode",
            "modbus/inverter/storedge_control/storage_ac_charge_policy",
            "modbus/inverter/storedge_control/storage_ac_charge_limit",
            "modbus/inverter/storedge_control/storage_backup_reserved_setting",
            "modbus/inverter/storedge_control/storage_default_mode",
            "modbus/inverter/storedge_control/remote_control_command_timeout",
            "modbus/inverter/storedge_control/remote_control_command_mode",
            "modbus/inverter/storedge_control/remote_control_charge_limit",
            "modbus/inverter/storedge_control/remote_control_discharge_limit",
        }

    @pytest.mark.asyncio
    async def test_async_init_does_nothing_when_disabled(
        self, mock_service_settings, mock_event_bus
    ):
        """Test async_init emits nothing when storedge control is disabled."""
        mock_service_settings.modbus.storedge_control_enabled = False

        control = StorEdgeControl(mock_service_settings)
        await control.async_init()

        mock_event_bus.emit.assert_not_called()


class TestStorEdgeControlCacheStoredgeControl:
    """Tests for StorEdgeControl.cache_storedge_control."""

    @pytest.mark.asyncio
    async def test_caches_last_known_from_units_with_storedge_control(
        self, mock_service_settings, mock_event_bus
    ):
        """Test the last known StorEdge state is cached per unit."""
        control = StorEdgeControl(mock_service_settings)

        last_known = make_last_known(storage_control_mode=4)
        unit = MagicMock()
        unit.inverter.storedge_control = last_known
        event = MagicMock()
        event.units = {"leader": unit}

        await control.cache_storedge_control(event)

        assert control._is_remote_control_active("leader") is True
        assert control._last_known["leader"] is last_known

    @pytest.mark.asyncio
    async def test_skips_units_without_storedge_control(
        self, mock_service_settings, mock_event_bus
    ):
        """Test units without a decoded StorEdge block are skipped, not cached."""
        control = StorEdgeControl(mock_service_settings)

        unit = MagicMock()
        unit.inverter.storedge_control = None
        event = MagicMock()
        event.units = {"leader": unit}

        await control.cache_storedge_control(event)

        assert control._is_remote_control_active("leader") is False
        assert "leader" not in control._last_known


class TestStorEdgeControlAlwaysAllowedWriteHandlers:
    """Tests for the write handlers that don't require Remote Control mode."""

    @pytest.mark.asyncio
    async def test_handle_storage_control_mode_writes(
        self, mock_service_settings, mock_event_bus
    ):
        """Test storage_control_mode writes even without Remote Control active."""
        control = StorEdgeControl(mock_service_settings)

        event = StoredgeControlModeEvent(
            topic="modbus/inverter/storedge_control/storage_control_mode",
            input=StoredgeControlModeInput(mode=4),
        )
        await control.handle_storage_control_mode(event)

        mock_event_bus.emit.assert_called_once()
        written = mock_event_bus.emit.call_args_list[0][0][0]
        assert written.register == SunSpecStorEdgeControlRegister.STORAGE_CONTROL_MODE
        assert written.payload == 4
        assert written.unit_key == "leader"

    @pytest.mark.asyncio
    async def test_handle_storage_ac_charge_policy_writes(
        self, mock_service_settings, mock_event_bus
    ):
        """Test storage_ac_charge_policy writes unconditionally."""
        control = StorEdgeControl(mock_service_settings)

        event = StoredgeAcChargePolicyEvent(
            topic="modbus/inverter/storedge_control/storage_ac_charge_policy",
            input=StoredgeAcChargePolicyInput(policy=1),
        )
        await control.handle_storage_ac_charge_policy(event)

        written = mock_event_bus.emit.call_args_list[0][0][0]
        assert (
            written.register == SunSpecStorEdgeControlRegister.STORAGE_AC_CHARGE_POLICY
        )
        assert written.payload == 1

    @pytest.mark.asyncio
    async def test_handle_storage_ac_charge_limit_writes(
        self, mock_service_settings, mock_event_bus
    ):
        """Test storage_ac_charge_limit writes unconditionally."""
        control = StorEdgeControl(mock_service_settings)

        event = StoredgeAcChargeLimitEvent(
            topic="modbus/inverter/storedge_control/storage_ac_charge_limit",
            input=StoredgeAcChargeLimitInput(limit=2500.0),
        )
        await control.handle_storage_ac_charge_limit(event)

        written = mock_event_bus.emit.call_args_list[0][0][0]
        assert (
            written.register == SunSpecStorEdgeControlRegister.STORAGE_AC_CHARGE_LIMIT
        )
        assert written.payload == pytest.approx(2500.0)

    @pytest.mark.asyncio
    async def test_handle_storage_backup_reserved_setting_writes(
        self, mock_service_settings, mock_event_bus
    ):
        """Test storage_backup_reserved_setting writes unconditionally."""
        control = StorEdgeControl(mock_service_settings)

        event = StoredgeBackupReservedSettingEvent(
            topic=("modbus/inverter/storedge_control/storage_backup_reserved_setting"),
            input=StoredgeBackupReservedSettingInput(percentage=10.0),
        )
        await control.handle_storage_backup_reserved_setting(event)

        written = mock_event_bus.emit.call_args_list[0][0][0]
        assert (
            written.register
            == SunSpecStorEdgeControlRegister.STORAGE_BACKUP_RESERVED_SETTING
        )
        assert written.payload == pytest.approx(10.0)


class TestStorEdgeControlRemoteControlGatedWriteHandlers:
    """Tests for the write handlers gated behind Remote Control mode."""

    @pytest.mark.asyncio
    async def test_handle_storage_default_mode_rejected_when_not_remote_control(
        self, mock_service_settings, mock_event_bus
    ):
        """Test the write is rejected when storage_control_mode isn't cached as 4."""
        control = StorEdgeControl(mock_service_settings)

        event = StoredgeDefaultModeEvent(
            topic="modbus/inverter/storedge_control/storage_default_mode",
            input=StoredgeDefaultModeInput(mode=0),
        )
        await control.handle_storage_default_mode(event)

        mock_event_bus.emit.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_storage_default_mode_writes_when_remote_control_active(
        self, mock_service_settings, mock_event_bus
    ):
        """Test the write goes through once Remote Control mode is cached."""
        control = StorEdgeControl(mock_service_settings)
        control._last_known["leader"] = make_last_known()

        event = StoredgeDefaultModeEvent(
            topic="modbus/inverter/storedge_control/storage_default_mode",
            input=StoredgeDefaultModeInput(mode=0),
        )
        await control.handle_storage_default_mode(event)

        written = mock_event_bus.emit.call_args_list[0][0][0]
        assert written.register == SunSpecStorEdgeControlRegister.STORAGE_DEFAULT_MODE
        assert written.payload == 0

    @pytest.mark.asyncio
    async def test_handle_remote_control_command_timeout_gated(
        self, mock_service_settings, mock_event_bus
    ):
        """Test remote_control_command_timeout is gated behind Remote Control mode."""
        control = StorEdgeControl(mock_service_settings)

        event = StoredgeRemoteControlCommandTimeoutEvent(
            topic=("modbus/inverter/storedge_control/remote_control_command_timeout"),
            input=StoredgeRemoteControlCommandTimeoutInput(seconds=3600),
        )
        await control.handle_remote_control_command_timeout(event)
        mock_event_bus.emit.assert_not_called()

        control._last_known["leader"] = make_last_known()
        await control.handle_remote_control_command_timeout(event)

        written = mock_event_bus.emit.call_args_list[0][0][0]
        assert (
            written.register
            == SunSpecStorEdgeControlRegister.REMOTE_CONTROL_COMMAND_TIMEOUT
        )
        assert written.payload == 3600

    @pytest.mark.asyncio
    async def test_handle_remote_control_command_mode_gated(
        self, mock_service_settings, mock_event_bus
    ):
        """Test remote_control_command_mode is gated behind Remote Control mode."""
        control = StorEdgeControl(mock_service_settings)
        control._last_known["leader"] = make_last_known()

        event = StoredgeRemoteControlCommandModeEvent(
            topic=("modbus/inverter/storedge_control/remote_control_command_mode"),
            input=StoredgeRemoteControlCommandModeInput(mode=1),
        )
        await control.handle_remote_control_command_mode(event)

        written = mock_event_bus.emit.call_args_list[0][0][0]
        assert (
            written.register
            == SunSpecStorEdgeControlRegister.REMOTE_CONTROL_COMMAND_MODE
        )
        assert written.payload == 1

    @pytest.mark.asyncio
    async def test_handle_remote_control_charge_limit_gated(
        self, mock_service_settings, mock_event_bus
    ):
        """Test remote_control_charge_limit is rejected when mode isn't 4."""
        control = StorEdgeControl(mock_service_settings)
        control._last_known["leader"] = make_last_known(storage_control_mode=1)

        event = StoredgeRemoteControlChargeLimitEvent(
            topic=("modbus/inverter/storedge_control/remote_control_charge_limit"),
            input=StoredgeRemoteControlChargeLimitInput(limit=5000.0),
        )
        await control.handle_remote_control_charge_limit(event)

        mock_event_bus.emit.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_remote_control_discharge_limit_writes_when_active(
        self, mock_service_settings, mock_event_bus
    ):
        """Test remote_control_discharge_limit writes once mode is 4."""
        control = StorEdgeControl(mock_service_settings)
        control._last_known["leader"] = make_last_known()

        event = StoredgeRemoteControlDischargeLimitEvent(
            topic=("modbus/inverter/storedge_control/remote_control_discharge_limit"),
            input=StoredgeRemoteControlDischargeLimitInput(limit=5000.0),
        )
        await control.handle_remote_control_discharge_limit(event)

        written = mock_event_bus.emit.call_args_list[0][0][0]
        assert (
            written.register
            == SunSpecStorEdgeControlRegister.REMOTE_CONTROL_DISCHARGE_LIMIT
        )
        assert written.payload == pytest.approx(5000.0)


class TestStorEdgeControlNoopWrites:
    """Tests that a write matching the last known value is skipped."""

    @pytest.mark.asyncio
    async def test_always_allowed_field_skips_when_value_unchanged(
        self, mock_service_settings, mock_event_bus
    ):
        """Test an always-allowed field is not rewritten when already at that value."""
        control = StorEdgeControl(mock_service_settings)
        control._last_known["leader"] = make_last_known(storage_control_mode=4)

        event = StoredgeControlModeEvent(
            topic="modbus/inverter/storedge_control/storage_control_mode",
            input=StoredgeControlModeInput(mode=4),
        )
        await control.handle_storage_control_mode(event)

        mock_event_bus.emit.assert_not_called()

    @pytest.mark.asyncio
    async def test_always_allowed_field_writes_when_value_changed(
        self, mock_service_settings, mock_event_bus
    ):
        """Test the same field still writes when the requested value differs."""
        control = StorEdgeControl(mock_service_settings)
        control._last_known["leader"] = make_last_known(storage_control_mode=1)

        event = StoredgeControlModeEvent(
            topic="modbus/inverter/storedge_control/storage_control_mode",
            input=StoredgeControlModeInput(mode=4),
        )
        await control.handle_storage_control_mode(event)

        mock_event_bus.emit.assert_called_once()

    @pytest.mark.asyncio
    async def test_gated_field_skips_when_value_unchanged_even_if_not_remote_control(
        self, mock_service_settings, mock_event_bus
    ):
        """Test a no-op write is skipped before the Remote Control gate is checked."""
        control = StorEdgeControl(mock_service_settings)
        control._last_known["leader"] = make_last_known(
            storage_control_mode=1, storage_default_mode=6
        )

        event = StoredgeDefaultModeEvent(
            topic="modbus/inverter/storedge_control/storage_default_mode",
            input=StoredgeDefaultModeInput(mode=6),
        )
        await control.handle_storage_default_mode(event)

        mock_event_bus.emit.assert_not_called()

    @pytest.mark.asyncio
    async def test_gated_field_writes_when_value_changed_and_remote_control_active(
        self, mock_service_settings, mock_event_bus
    ):
        """Test a genuinely different value still writes once gated and unchanged."""
        control = StorEdgeControl(mock_service_settings)
        control._last_known["leader"] = make_last_known(
            storage_control_mode=4, storage_default_mode=6
        )

        event = StoredgeDefaultModeEvent(
            topic="modbus/inverter/storedge_control/storage_default_mode",
            input=StoredgeDefaultModeInput(mode=0),
        )
        await control.handle_storage_default_mode(event)

        mock_event_bus.emit.assert_called_once()


class TestStorEdgeControlForceWrites:
    """Tests for the force flag bypassing no-op write skipping."""

    @pytest.mark.asyncio
    async def test_always_allowed_field_force_writes_despite_unchanged_value(
        self, mock_service_settings, mock_event_bus
    ):
        """Test force=True re-sends an always-allowed field even if unchanged."""
        control = StorEdgeControl(mock_service_settings)
        control._last_known["leader"] = make_last_known(storage_control_mode=4)

        event = StoredgeControlModeEvent(
            topic="modbus/inverter/storedge_control/storage_control_mode",
            input=StoredgeControlModeInput(mode=4, force=True),
        )
        await control.handle_storage_control_mode(event)

        written = mock_event_bus.emit.call_args_list[0][0][0]
        assert written.register == SunSpecStorEdgeControlRegister.STORAGE_CONTROL_MODE
        assert written.payload == 4

    @pytest.mark.asyncio
    async def test_gated_field_force_writes_despite_unchanged_value(
        self, mock_service_settings, mock_event_bus
    ):
        """Test force=True re-sends a gated field once Remote Control is active."""
        control = StorEdgeControl(mock_service_settings)
        control._last_known["leader"] = make_last_known(
            storage_control_mode=4, storage_default_mode=6
        )

        event = StoredgeDefaultModeEvent(
            topic="modbus/inverter/storedge_control/storage_default_mode",
            input=StoredgeDefaultModeInput(mode=6, force=True),
        )
        await control.handle_storage_default_mode(event)

        written = mock_event_bus.emit.call_args_list[0][0][0]
        assert written.register == SunSpecStorEdgeControlRegister.STORAGE_DEFAULT_MODE
        assert written.payload == 6

    @pytest.mark.asyncio
    async def test_force_does_not_bypass_remote_control_gate(
        self, mock_service_settings, mock_event_bus
    ):
        """Test force=True still respects the Remote Control gate."""
        control = StorEdgeControl(mock_service_settings)
        control._last_known["leader"] = make_last_known(
            storage_control_mode=1, storage_default_mode=6
        )

        event = StoredgeDefaultModeEvent(
            topic="modbus/inverter/storedge_control/storage_default_mode",
            input=StoredgeDefaultModeInput(mode=6, force=True),
        )
        await control.handle_storage_default_mode(event)

        mock_event_bus.emit.assert_not_called()

    def test_bare_scalar_payload_still_wraps_with_force_false(self):
        """Test a bare scalar payload keeps working and defaults force to False."""
        input_model = StoredgeControlModeInput.model_validate(4)

        assert input_model.mode == 4
        assert input_model.force is False

    def test_json_payload_can_set_force_true(self):
        """Test a JSON object payload can opt into force."""
        input_model = StoredgeControlModeInput.model_validate(
            {"mode": 4, "force": True}
        )

        assert input_model.mode == 4
        assert input_model.force is True


class TestStorEdgeControlInputValidation:
    """Tests for the input model validation ranges."""

    @pytest.mark.parametrize("value", [0, 4])
    def test_storage_control_mode_valid_bounds(self, value):
        """Test StoredgeControlModeInput accepts its documented bounds."""
        assert StoredgeControlModeInput(mode=value).mode == value

    @pytest.mark.parametrize("value", [-1, 5])
    def test_storage_control_mode_rejects_out_of_range(self, value):
        """Test StoredgeControlModeInput rejects out-of-range values."""
        with pytest.raises(ValidationError):
            StoredgeControlModeInput(mode=value)

    @pytest.mark.parametrize("value", [-1, 4])
    def test_storage_ac_charge_policy_rejects_out_of_range(self, value):
        """Test StoredgeAcChargePolicyInput rejects out-of-range values."""
        with pytest.raises(ValidationError):
            StoredgeAcChargePolicyInput(policy=value)

    def test_storage_ac_charge_limit_rejects_negative(self):
        """Test StoredgeAcChargeLimitInput rejects negative values."""
        with pytest.raises(ValidationError):
            StoredgeAcChargeLimitInput(limit=-1.0)

    @pytest.mark.parametrize("value", [-1, 101])
    def test_storage_backup_reserved_setting_rejects_out_of_range(self, value):
        """Test StoredgeBackupReservedSettingInput rejects out-of-range values."""
        with pytest.raises(ValidationError):
            StoredgeBackupReservedSettingInput(percentage=value)

    @pytest.mark.parametrize("value", [-1, 8])
    def test_storage_default_mode_rejects_out_of_range(self, value):
        """Test StoredgeDefaultModeInput rejects out-of-range values."""
        with pytest.raises(ValidationError):
            StoredgeDefaultModeInput(mode=value)

    @pytest.mark.parametrize("value", [-1, 86401])
    def test_remote_control_command_timeout_rejects_out_of_range(self, value):
        """Test StoredgeRemoteControlCommandTimeoutInput rejects out-of-range values."""
        with pytest.raises(ValidationError):
            StoredgeRemoteControlCommandTimeoutInput(seconds=value)

    @pytest.mark.parametrize("value", [-1, 8])
    def test_remote_control_command_mode_rejects_out_of_range(self, value):
        """Test StoredgeRemoteControlCommandModeInput rejects out-of-range values."""
        with pytest.raises(ValidationError):
            StoredgeRemoteControlCommandModeInput(mode=value)

    def test_remote_control_charge_limit_rejects_negative(self):
        """Test StoredgeRemoteControlChargeLimitInput rejects negative values."""
        with pytest.raises(ValidationError):
            StoredgeRemoteControlChargeLimitInput(limit=-1.0)

    def test_remote_control_discharge_limit_rejects_negative(self):
        """Test StoredgeRemoteControlDischargeLimitInput rejects negative values."""
        with pytest.raises(ValidationError):
            StoredgeRemoteControlDischargeLimitInput(limit=-1.0)

    def test_scalar_input_wraps_bare_value(self):
        """Test a bare scalar MQTT payload (not a dict) still validates."""
        assert StoredgeControlModeInput.model_validate(4).mode == 4
