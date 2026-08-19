#!/usr/bin/env python3
"""Import an existing InfluxDB history into the local storage database."""

import argparse
import asyncio
from datetime import datetime, timezone
from glob import glob
from os import environ, path
from pathlib import Path
from typing import Any

import yaml

from solaredge2mqtt.core.exceptions import ConfigurationException
from solaredge2mqtt.core.logging import initialize_logging, logger
from solaredge2mqtt.core.settings import service_settings
from solaredge2mqtt.core.settings.migrator import SecretReference
from solaredge2mqtt.core.settings.upgrades import RawConfigLoader
from solaredge2mqtt.core.storage import Point, StorageService
from solaredge2mqtt.core.storage.influx_import import (
    InfluxCredentials,
    import_from_influxdb,
    import_from_line_protocol,
    measurements_to_import,
)
from solaredge2mqtt.services.weather.models import OpenWeatherMapBaseData

TRAINING_MEASUREMENT = "forecast_training"

#: Stored next to the weather features and not part of the canonical schema.
PASSTHROUGH_FIELDS = ("energy", "power")

DEFAULT_START = datetime(1970, 1, 1, tzinfo=timezone.utc)


def training_point_to_canonical(point: Point) -> Point | None:
    """Convert a stored OpenWeatherMap snapshot onto the canonical schema.

    Releases before the local storage kept the provider's own field names in
    `forecast_training` and translated them on every read. The storage now
    holds the canonical schema, so the translation happens once, here. Fields
    without a canonical counterpart are dropped, and every converted snapshot
    is stamped with the provider that wrote it.
    """
    if point.measurement != TRAINING_MEASUREMENT:
        return point

    converted = Point(point.measurement)
    converted.tags = dict(point.tags)
    converted.timestamp = point.timestamp

    for field, value in point.fields.items():
        if field in PASSTHROUGH_FIELDS:
            converted.field(field, value)
            continue

        translated = OpenWeatherMapBaseData.to_canonical_field(field, value)
        if translated is None or translated[1] is None:
            continue

        converted.field(*translated)

    if not converted.fields:
        return None

    converted.field(
        OpenWeatherMapBaseData.PROVIDER_FIELD, OpenWeatherMapBaseData.PROVIDER_NAME
    )

    return converted


ENV_PREFIX = "SE2MQTT_INFLUXDB__"


def legacy_configuration_files(config_dir: str) -> list[str]:
    """The configuration and its backups, newest first.

    Starting the service upgrades the configuration and drops the influxdb
    section, so the credentials usually live in the backup the upgrade wrote
    rather than in the configuration itself.
    """
    config_file = path.join(config_dir, "configuration.yml")
    backups = sorted(glob(f"{config_file}.backup.*"), reverse=True)

    return [config_file, *backups]


def read_legacy_influxdb_section(config_dir: str) -> dict[str, Any]:
    """Read the influxdb section of the configuration or of its newest backup."""
    secrets_file = path.join(config_dir, "secrets.yml")

    influxdb = None
    for candidate in legacy_configuration_files(config_dir):
        if not path.exists(candidate):
            continue

        with open(candidate, "r", encoding="utf-8") as file:
            config_data = yaml.load(file, Loader=RawConfigLoader) or {}

        section = config_data.get("influxdb")
        if isinstance(section, dict):
            logger.info(f"Reading InfluxDB credentials from {candidate}")
            influxdb = section
            break

    if influxdb is None:
        return {}

    secrets: dict[str, Any] = {}
    if path.exists(secrets_file):
        with open(secrets_file, "r", encoding="utf-8") as file:
            secrets = yaml.safe_load(file) or {}

    resolved = dict(influxdb)
    token = resolved.get("token")
    if isinstance(token, SecretReference):
        resolved["token"] = secrets.get(token.secret_key)

    return resolved


def build_credentials(arguments: argparse.Namespace) -> InfluxCredentials:
    """Combine command line arguments, the old configuration and the environment."""
    legacy = read_legacy_influxdb_section(arguments.config_dir)

    host = arguments.url or legacy.get("host") or environ.get(f"{ENV_PREFIX}HOST")
    port = legacy.get("port") or environ.get(f"{ENV_PREFIX}PORT") or 8086
    token = arguments.token or legacy.get("token") or environ.get(f"{ENV_PREFIX}TOKEN")
    org = arguments.org or legacy.get("org") or environ.get(f"{ENV_PREFIX}ORG")
    bucket = (
        arguments.bucket
        or legacy.get("bucket")
        or environ.get(f"{ENV_PREFIX}BUCKET")
        or "solaredge"
    )

    if host is None:
        raise ConfigurationException("storage", "No InfluxDB host configured or given.")

    url = str(host)
    if arguments.url is None and not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    if ":" not in url.split("//", 1)[-1]:
        url = f"{url}:{port}"

    return InfluxCredentials(url, str(token or ""), str(org or ""), str(bucket))


async def _run(arguments: argparse.Namespace) -> None:
    """Import the history into the storage.

    The credentials are read before `service_settings`, which upgrades the
    configuration and takes the influxdb section with it.
    """
    credentials = (
        None if arguments.from_lp is not None else build_credentials(arguments)
    )

    settings = service_settings(arguments.config_dir)
    initialize_logging(settings.logging_level)

    storage = StorageService(settings.storage, settings.prices, arguments.config_dir)
    await storage.async_init()

    imported = 0

    try:
        if arguments.from_lp is not None:
            imported = await import_from_line_protocol(
                storage,
                Path(arguments.from_lp),
                arguments.dry_run,
                training_point_to_canonical,
            )
        elif credentials is not None:
            imported = await import_from_influxdb(
                storage,
                credentials,
                _parse_time(arguments.start, DEFAULT_START),
                _parse_time(arguments.stop, datetime.now(tz=timezone.utc)),
                measurements_to_import(arguments.measurements, arguments.include_raw),
                arguments.slice_days,
                arguments.dry_run,
                arguments.resume,
                training_point_to_canonical,
            )

        logger.info(f"Import finished, {imported} points processed")
    finally:
        await storage.close()


def _parse_time(value: str | None, default: datetime) -> datetime:
    if value is None:
        return default

    moment = datetime.fromisoformat(value)

    return moment if moment.tzinfo is not None else moment.replace(tzinfo=timezone.utc)


def _measurement_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def main() -> None:
    """Entry point of the solaredge2mqtt-migrate-influxdb console script."""
    parser = argparse.ArgumentParser(
        description=(
            "Import the history of an InfluxDB 2.x bucket into the local "
            "storage database. The import is idempotent and can be repeated."
        )
    )
    parser.add_argument("--config-dir", type=str, default="config")
    parser.add_argument("--url", type=str, default=None)
    parser.add_argument("--token", type=str, default=None)
    parser.add_argument("--org", type=str, default=None)
    parser.add_argument("--bucket", type=str, default=None)
    parser.add_argument(
        "--from-lp",
        type=str,
        default=None,
        help="Import a line protocol dump instead of querying a running InfluxDB",
    )
    parser.add_argument("--start", type=str, default=None)
    parser.add_argument("--stop", type=str, default=None)
    parser.add_argument(
        "--measurements",
        type=_measurement_list,
        default=None,
        help="Comma separated list, defaults to everything but the raw samples",
    )
    parser.add_argument("--include-raw", action="store_true")
    parser.add_argument("--slice-days", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action="store_true")

    arguments = parser.parse_args()

    try:
        asyncio.run(_run(arguments))
    except ConfigurationException as error:
        logger.error(f"Configuration error: {error.message}")
    except KeyboardInterrupt:
        logger.info("Import interrupted by user")


if __name__ == "__main__":
    main()
