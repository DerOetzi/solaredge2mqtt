from solaredge2mqtt.core.mqtt.events import MQTTReceivedEvent, MQTTSubscribeEvent
from solaredge2mqtt.services.modbus.storedge_control_inputs import (
    RemoteControlChargeLimitInput,
    RemoteControlCommandModeInput,
    RemoteControlCommandTimeoutInput,
    RemoteControlDischargeLimitInput,
    StorageAcChargeLimitInput,
    StorageAcChargePolicyInput,
    StorageBackupReservedSettingInput,
    StorageControlModeInput,
    StorageDefaultModeInput,
)


class StorageControlModeEvent(
    MQTTReceivedEvent[StorageControlModeInput]
): ...  # pragma: no cover


class StorageControlModeSubscribeEvent(
    MQTTSubscribeEvent[StorageControlModeEvent]
): ...  # pragma: no cover


class StorageAcChargePolicyEvent(
    MQTTReceivedEvent[StorageAcChargePolicyInput]
): ...  # pragma: no cover


class StorageAcChargePolicySubscribeEvent(
    MQTTSubscribeEvent[StorageAcChargePolicyEvent]
): ...  # pragma: no cover


class StorageAcChargeLimitEvent(
    MQTTReceivedEvent[StorageAcChargeLimitInput]
): ...  # pragma: no cover


class StorageAcChargeLimitSubscribeEvent(
    MQTTSubscribeEvent[StorageAcChargeLimitEvent]
): ...  # pragma: no cover


class StorageBackupReservedSettingEvent(
    MQTTReceivedEvent[StorageBackupReservedSettingInput]
): ...  # pragma: no cover


class StorageBackupReservedSettingSubscribeEvent(
    MQTTSubscribeEvent[StorageBackupReservedSettingEvent]
): ...  # pragma: no cover


class StorageDefaultModeEvent(
    MQTTReceivedEvent[StorageDefaultModeInput]
): ...  # pragma: no cover


class StorageDefaultModeSubscribeEvent(
    MQTTSubscribeEvent[StorageDefaultModeEvent]
): ...  # pragma: no cover


class RemoteControlCommandTimeoutEvent(
    MQTTReceivedEvent[RemoteControlCommandTimeoutInput]
): ...  # pragma: no cover


class RemoteControlCommandTimeoutSubscribeEvent(
    MQTTSubscribeEvent[RemoteControlCommandTimeoutEvent]
): ...  # pragma: no cover


class RemoteControlCommandModeEvent(
    MQTTReceivedEvent[RemoteControlCommandModeInput]
): ...  # pragma: no cover


class RemoteControlCommandModeSubscribeEvent(
    MQTTSubscribeEvent[RemoteControlCommandModeEvent]
): ...  # pragma: no cover


class RemoteControlChargeLimitEvent(
    MQTTReceivedEvent[RemoteControlChargeLimitInput]
): ...  # pragma: no cover


class RemoteControlChargeLimitSubscribeEvent(
    MQTTSubscribeEvent[RemoteControlChargeLimitEvent]
): ...  # pragma: no cover


class RemoteControlDischargeLimitEvent(
    MQTTReceivedEvent[RemoteControlDischargeLimitInput]
): ...  # pragma: no cover


class RemoteControlDischargeLimitSubscribeEvent(
    MQTTSubscribeEvent[RemoteControlDischargeLimitEvent]
): ...  # pragma: no cover
