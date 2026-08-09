from solaredge2mqtt.core.mqtt.events import MQTTReceivedEvent, MQTTSubscribeEvent
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


class StoredgeControlModeEvent(
    MQTTReceivedEvent[StoredgeControlModeInput]
): ...  # pragma: no cover


class StoredgeControlModeSubscribeEvent(
    MQTTSubscribeEvent[StoredgeControlModeEvent]
): ...  # pragma: no cover


class StoredgeAcChargePolicyEvent(
    MQTTReceivedEvent[StoredgeAcChargePolicyInput]
): ...  # pragma: no cover


class StoredgeAcChargePolicySubscribeEvent(
    MQTTSubscribeEvent[StoredgeAcChargePolicyEvent]
): ...  # pragma: no cover


class StoredgeAcChargeLimitEvent(
    MQTTReceivedEvent[StoredgeAcChargeLimitInput]
): ...  # pragma: no cover


class StoredgeAcChargeLimitSubscribeEvent(
    MQTTSubscribeEvent[StoredgeAcChargeLimitEvent]
): ...  # pragma: no cover


class StoredgeBackupReservedSettingEvent(
    MQTTReceivedEvent[StoredgeBackupReservedSettingInput]
): ...  # pragma: no cover


class StoredgeBackupReservedSettingSubscribeEvent(
    MQTTSubscribeEvent[StoredgeBackupReservedSettingEvent]
): ...  # pragma: no cover


class StoredgeDefaultModeEvent(
    MQTTReceivedEvent[StoredgeDefaultModeInput]
): ...  # pragma: no cover


class StoredgeDefaultModeSubscribeEvent(
    MQTTSubscribeEvent[StoredgeDefaultModeEvent]
): ...  # pragma: no cover


class StoredgeRemoteControlCommandTimeoutEvent(
    MQTTReceivedEvent[StoredgeRemoteControlCommandTimeoutInput]
): ...  # pragma: no cover


class StoredgeRemoteControlCommandTimeoutSubscribeEvent(
    MQTTSubscribeEvent[StoredgeRemoteControlCommandTimeoutEvent]
): ...  # pragma: no cover


class StoredgeRemoteControlCommandModeEvent(
    MQTTReceivedEvent[StoredgeRemoteControlCommandModeInput]
): ...  # pragma: no cover


class StoredgeRemoteControlCommandModeSubscribeEvent(
    MQTTSubscribeEvent[StoredgeRemoteControlCommandModeEvent]
): ...  # pragma: no cover


class StoredgeRemoteControlChargeLimitEvent(
    MQTTReceivedEvent[StoredgeRemoteControlChargeLimitInput]
): ...  # pragma: no cover


class StoredgeRemoteControlChargeLimitSubscribeEvent(
    MQTTSubscribeEvent[StoredgeRemoteControlChargeLimitEvent]
): ...  # pragma: no cover


class StoredgeRemoteControlDischargeLimitEvent(
    MQTTReceivedEvent[StoredgeRemoteControlDischargeLimitInput]
): ...  # pragma: no cover


class StoredgeRemoteControlDischargeLimitSubscribeEvent(
    MQTTSubscribeEvent[StoredgeRemoteControlDischargeLimitEvent]
): ...  # pragma: no cover
