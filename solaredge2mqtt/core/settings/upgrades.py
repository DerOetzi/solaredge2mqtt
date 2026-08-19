from __future__ import annotations

from datetime import datetime
from os import path
from shutil import copy2
from typing import Any, Callable

import yaml

from solaredge2mqtt.core.logging import logger
from solaredge2mqtt.core.settings.migrator import ConfigDumper, SecretReference

CONFIG_VERSION = 1

CONFIG_VERSION_KEY = "config_version"

CARRIED_INFLUXDB_KEYS = ("retention_raw", "debounce_cycles")


class RawConfigLoader(yaml.SafeLoader): ...  # pragma: no cover


def _raw_secret_constructor(
    loader: RawConfigLoader, node: yaml.ScalarNode
) -> SecretReference:
    return SecretReference(loader.construct_scalar(node))


RawConfigLoader.add_constructor("!secret", _raw_secret_constructor)


def _influxdb_to_storage(config_data: dict[str, Any]) -> dict[str, Any]:
    influxdb = config_data.pop("influxdb", None)

    if influxdb is None:
        return config_data

    logger.warning(
        "InfluxDB has been replaced by a local storage database. "
        "The 'influxdb' configuration section is removed. "
        "Run 'solaredge2mqtt-migrate-influxdb' to import the existing history."
    )

    storage = dict(config_data.get("storage") or {})
    storage.setdefault("enable", True)

    for key in CARRIED_INFLUXDB_KEYS:
        if key in influxdb and key not in storage:
            storage[key] = influxdb[key]

    config_data["storage"] = storage

    return config_data


UPGRADES: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] = {
    1: _influxdb_to_storage
}


def upgrade_configuration(config_file: str) -> bool:
    config_data = _read_raw_configuration(config_file)

    current = int(config_data.get(CONFIG_VERSION_KEY, 0))

    if current >= CONFIG_VERSION:
        return False

    for version in range(current + 1, CONFIG_VERSION + 1):
        config_data = UPGRADES[version](config_data)

    config_data[CONFIG_VERSION_KEY] = CONFIG_VERSION

    _backup_configuration(config_file)
    _write_raw_configuration(config_file, config_data)

    logger.info(f"Upgraded {config_file} to configuration version {CONFIG_VERSION}")

    return True


def _read_raw_configuration(config_file: str) -> dict[str, Any]:
    with open(config_file, "r", encoding="utf-8") as file:
        data = yaml.load(file, Loader=RawConfigLoader)

    return data if data is not None else {}


def _write_raw_configuration(config_file: str, config_data: dict[str, Any]) -> None:
    with open(config_file, "w", encoding="utf-8") as file:
        yaml.dump(
            config_data,
            file,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
            Dumper=ConfigDumper,
        )


def _backup_configuration(config_file: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backup_file = f"{config_file}.backup.{stamp}"

    if not path.exists(backup_file):
        copy2(config_file, backup_file)
        logger.info(f"Backed up configuration to {backup_file}")

    return backup_file
