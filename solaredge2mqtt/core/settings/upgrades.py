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

MIGRATION_COMMAND = "solaredge2mqtt-migrate-influxdb"

#: Never resolved into the logged command -- a token in the service log is a
#: token in journald, in the Docker logs and in every log someone attaches to
#: an issue. The upgrade leaves secrets.yml alone, so it stays available.
TOKEN_PLACEHOLDER = "YOUR_INFLUXDB_TOKEN"

DEFAULT_INFLUXDB_PORT = 8086


class RawConfigLoader(yaml.SafeLoader): ...  # pragma: no cover


def _raw_secret_constructor(
    loader: RawConfigLoader, node: yaml.ScalarNode
) -> SecretReference:
    return SecretReference(loader.construct_scalar(node))


RawConfigLoader.add_constructor("!secret", _raw_secret_constructor)


def influx_url(host: Any, port: Any = None) -> str:
    """The base URL of an InfluxDB, built as the removed settings model did."""
    url = str(host)

    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    if ":" not in url.split("//", 1)[-1]:
        url = f"{url}:{port or DEFAULT_INFLUXDB_PORT}"

    return url


def migration_command(influxdb: dict[str, Any], config_dir: str) -> str:
    """The import command for a configuration that is about to lose its section.

    The section is the only place the host, the organization and the bucket
    are written down, and the upgrade removes it, so the command is spelled
    out while they are still known.
    """
    parts = [MIGRATION_COMMAND, "--config-dir", config_dir]

    host = influxdb.get("host")
    if host is not None:
        parts += ["--url", influx_url(host, influxdb.get("port"))]

    for key in ("org", "bucket"):
        value = influxdb.get(key)
        if value is not None:
            parts += [f"--{key}", str(value)]

    parts += ["--token", TOKEN_PLACEHOLDER]

    return " ".join(parts)


def _influxdb_to_storage(config_data: dict[str, Any], config_file: str) -> bool:
    influxdb = config_data.pop("influxdb", None)

    if influxdb is None:
        return False

    config_dir = path.dirname(config_file) or "."

    logger.warning(
        "InfluxDB has been replaced by a local storage database and the "
        "'influxdb' configuration section is removed. Import the existing "
        "history with:"
    )
    logger.warning(f"  {migration_command(influxdb, config_dir)}")
    logger.warning(
        f"Replace {TOKEN_PLACEHOLDER} with the influxdb_token entry of "
        "secrets.yml, which this upgrade leaves untouched."
    )

    storage = dict(config_data.get("storage") or {})
    storage.setdefault("enable", True)

    for key in CARRIED_INFLUXDB_KEYS:
        if key in influxdb and key not in storage:
            storage[key] = influxdb[key]

    config_data["storage"] = storage

    return True


#: An upgrade mutates the configuration in place and reports whether it
#: changed anything. Only a changed file is rewritten, so a configuration
#: that needs no migration keeps its comments and its formatting.
UPGRADES: dict[int, Callable[[dict[str, Any], str], bool]] = {1: _influxdb_to_storage}


def upgrade_configuration(config_file: str) -> bool:
    config_data = _read_raw_configuration(config_file)

    current = int(config_data.get(CONFIG_VERSION_KEY, 0))

    if current >= CONFIG_VERSION:
        return False

    changed = False
    for version in range(current + 1, CONFIG_VERSION + 1):
        changed = UPGRADES[version](config_data, config_file) or changed

    if not changed:
        return False

    config_data[CONFIG_VERSION_KEY] = CONFIG_VERSION

    backup_file = _backup_configuration(config_file)
    _write_raw_configuration(config_file, config_data)

    logger.warning(
        f"Upgraded {config_file} to configuration version {CONFIG_VERSION}. "
        f"The previous file is kept as {backup_file}; comments and formatting "
        "of the rewritten file are not preserved."
    )

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
