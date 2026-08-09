from solaredge2mqtt.core.mqtt.events import MQTTReceivedEvent, MQTTSubscribeEvent
from solaredge2mqtt.services.modbus.storedge_control_inputs import (
    StoredgeAcChargeLimitInput,
    StoredgeAcChargePolicyInput,
    StoredgeBackupReservedSettingInput,
    StoredgeChargeLimitInput,
    StoredgeCommandModeInput,
    StoredgeCommandTimeoutInput,
    StoredgeControlModeInput,
    StoredgeDefaultModeInput,
    StoredgeDischargeLimitInput,
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


class StoredgeCommandTimeoutEvent(
    MQTTReceivedEvent[StoredgeCommandTimeoutInput]
): ...  # pragma: no cover


class StoredgeCommandTimeoutSubscribeEvent(
    MQTTSubscribeEvent[StoredgeCommandTimeoutEvent]
): ...  # pragma: no cover


class StoredgeCommandModeEvent(
    MQTTReceivedEvent[StoredgeCommandModeInput]
): ...  # pragma: no cover


class StoredgeCommandModeSubscribeEvent(
    MQTTSubscribeEvent[StoredgeCommandModeEvent]
): ...  # pragma: no cover


class StoredgeChargeLimitEvent(
    MQTTReceivedEvent[StoredgeChargeLimitInput]
): ...  # pragma: no cover


class StoredgeChargeLimitSubscribeEvent(
    MQTTSubscribeEvent[StoredgeChargeLimitEvent]
): ...  # pragma: no cover


class StoredgeDischargeLimitEvent(
    MQTTReceivedEvent[StoredgeDischargeLimitInput]
): ...  # pragma: no cover


class StoredgeDischargeLimitSubscribeEvent(
    MQTTSubscribeEvent[StoredgeDischargeLimitEvent]
): ...  # pragma: no cover
