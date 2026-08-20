from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Iterator

import aiohttp

from solaredge2mqtt.core.exceptions import ConfigurationException
from solaredge2mqtt.core.logging import logger
from solaredge2mqtt.core.storage.models import FieldValue, Point
from solaredge2mqtt.core.storage.queries import (
    DELETE_SERIES,
    MERGE_SERIES_POINTS,
    MODULE_SERIES_MERGE_PLAN,
)

if TYPE_CHECKING:
    from solaredge2mqtt.core.storage import StorageService

DEFAULT_MEASUREMENTS = (
    "energy",
    "powerflow",
    "battery",
    "forecast_training",
    "forecast",
    "modules",
)

RAW_MEASUREMENTS = ("powerflow_raw", "battery_raw")

RESERVED_COLUMNS = frozenset(
    {
        "result",
        "table",
        "_start",
        "_stop",
        "_time",
        "_measurement",
        "_field",
        "_value",
    }
)

CURSOR_KEY_PREFIX = "influx_import_cursor"

QUERY_TEMPLATE = (
    'from(bucket: "{bucket}")\n'
    "  |> range(start: {start}, stop: {stop})\n"
    '  |> filter(fn: (r) => r._measurement == "{measurement}")\n'
)

#: Without this the server picks its own dialect and omits the annotations.
DIALECT = {
    "annotations": ["group", "datatype", "default"],
    "delimiter": ",",
    "header": True,
}

NANOSECONDS_PER_SECOND = 1_000_000_000

#: A transform applied to every imported point. Returning None drops the point.
PointTransform = Callable[[Point], "Point | None"]

LINE_PROTOCOL_SUFFIXES = (".lp", ".txt")


class InfluxCredentials:
    def __init__(self, url: str, token: str, org: str, bucket: str) -> None:
        self.url: str = url.rstrip("/")
        self.token: str = token
        self.org: str = org
        self.bucket: str = bucket


def _cast(datatype: str, value: str) -> FieldValue | datetime | None:
    if value == "":
        return None

    if datatype in ("double", "float"):
        return float(value)

    if datatype in ("long", "unsignedLong"):
        return int(value)

    if datatype == "boolean":
        return value.lower() == "true"

    if datatype.startswith("dateTime"):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    return value


def parse_annotated_csv(payload: str) -> Iterator[Point]:
    """Turn an annotated CSV answer of the query API into points.

    A large answer is split into blocks separated by a blank line, and only
    the first block of a schema carries the annotations - the following ones
    repeat the header alone. The datatypes therefore stay in force until a
    new `#datatype` line replaces them, otherwise every column of a
    continuation block would be read as a string.
    """
    datatypes: list[str] = []
    header: list[str] = []

    for row in csv.reader(StringIO(payload)):
        if not row or not any(row):
            header = []
            continue

        if row[0] == "#datatype":
            datatypes = row[1:]
            header = []
            continue

        if row[0].startswith("#"):
            continue

        if not header:
            header = row[1:]
            continue

        record = {
            key: _cast(datatypes[index] if index < len(datatypes) else "string", value)
            for index, (key, value) in enumerate(zip(header, row[1:]))
        }

        point = _point_from_record(record)
        if point is not None:
            yield point


def _point_from_record(record: dict[str, Any]) -> Point | None:
    measurement = record.get("_measurement")
    field = record.get("_field")
    value = record.get("_value")
    moment = record.get("_time")

    if measurement is None or field is None or value is None or moment is None:
        return None

    if not isinstance(moment, datetime):
        moment = datetime.fromisoformat(str(moment).replace("Z", "+00:00"))

    point = Point(str(measurement)).field(str(field), value)
    point.time(moment)

    for key, tag_value in record.items():
        if key in RESERVED_COLUMNS or key.startswith("#"):
            continue
        if tag_value is None or tag_value == "":
            continue

        point.tag(key, str(tag_value))

    return point


def _split_unescaped(text: str, separator: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    escaped = False

    for character in text:
        if escaped:
            current.append(character)
            escaped = False
        elif character == "\\":
            escaped = True
        elif character == separator:
            parts.append("".join(current))
            current = []
        else:
            current.append(character)

    parts.append("".join(current))

    return parts


def _parse_field_value(raw: str) -> FieldValue:
    if raw.startswith('"') and raw.endswith('"'):
        return raw[1:-1]

    if raw.endswith("i"):
        return int(raw[:-1])

    if raw in ("t", "T", "true", "True", "TRUE"):
        return True

    if raw in ("f", "F", "false", "False", "FALSE"):
        return False

    return float(raw)


def parse_line_protocol(payload: str) -> Iterator[Point]:
    for line in payload.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        parts = _split_unescaped(line, " ")
        if len(parts) < 2:
            continue

        keys = _split_unescaped(parts[0], ",")
        measurement = keys[0]

        point = Point(measurement)

        for tag in keys[1:]:
            tag_key, _, tag_value = tag.partition("=")
            point.tag(tag_key, tag_value)

        for field in _split_unescaped(parts[1], ","):
            field_key, _, field_value = field.partition("=")
            point.field(field_key, _parse_field_value(field_value))

        if len(parts) > 2:
            point.time(
                datetime.fromtimestamp(
                    int(parts[2]) / NANOSECONDS_PER_SECOND, tz=timezone.utc
                )
            )

        yield point


async def read_line_protocol(source: Path) -> Iterator[Point]:
    files = sorted(source.iterdir()) if source.is_dir() else [source]

    points: list[Point] = []
    for file in files:
        if file.is_dir() or file.suffix not in LINE_PROTOCOL_SUFFIXES:
            continue

        points.extend(parse_line_protocol(file.read_text(encoding="utf-8")))

    return iter(points)


async def query_influxdb(
    session: aiohttp.ClientSession,
    credentials: InfluxCredentials,
    measurement: str,
    start: datetime,
    stop: datetime,
) -> str:
    """Run one slice of the export.

    The query is posted as JSON with an explicit dialect: a raw `vnd.flux`
    body leaves the dialect to the server, which then answers without the
    datatype annotation and turns every value into a string.
    """
    query = QUERY_TEMPLATE.format(
        bucket=credentials.bucket,
        measurement=measurement,
        start=start.isoformat().replace("+00:00", "Z"),
        stop=stop.isoformat().replace("+00:00", "Z"),
    )

    async with session.post(
        f"{credentials.url}/api/v2/query",
        params={"org": credentials.org},
        json={"query": query, "dialect": DIALECT},
        headers={
            "Authorization": f"Token {credentials.token}",
            "Accept": "application/csv",
        },
    ) as response:
        response.raise_for_status()
        return await response.text()


def measurements_to_import(
    measurements: list[str] | None, include_raw: bool
) -> list[str]:
    if measurements:
        return measurements

    if include_raw:
        return [*DEFAULT_MEASUREMENTS, *RAW_MEASUREMENTS]

    return list(DEFAULT_MEASUREMENTS)


def _written_values(points: list[Point]) -> int:
    """The number of rows the points write, one per field.

    A point may carry more fields than the record it came from -- the
    migration stamps the provider onto every weather snapshot -- so counting
    points would understate the import.
    """
    return sum(len(point.fields) for point in points)


def _transform(points: list[Point], transform: PointTransform | None) -> list[Point]:
    if transform is None:
        return points

    transformed = [transform(point) for point in points]

    return [point for point in transformed if point is not None]


async def import_from_line_protocol(
    storage: StorageService,
    source: Path,
    dry_run: bool = False,
    transform: PointTransform | None = None,
) -> int:
    points = _transform(list(await read_line_protocol(source)), transform)

    if not dry_run:
        await storage.write_points(points)

    values = _written_values(points)
    logger.info(f"Imported {values} values from {source}")

    return values


async def import_from_influxdb(
    storage: StorageService,
    credentials: InfluxCredentials,
    start: datetime,
    stop: datetime,
    measurements: list[str],
    slice_days: int = 1,
    dry_run: bool = False,
    resume: bool = False,
    transform: PointTransform | None = None,
) -> int:
    if credentials.token == "" or credentials.org == "":
        raise ConfigurationException(
            "storage", "InfluxDB token and organization are required for the import."
        )

    imported = 0

    async with aiohttp.ClientSession() as session:
        for measurement in measurements:
            imported += await _import_measurement(
                storage,
                session,
                credentials,
                measurement,
                await _resume_start(storage, measurement, start, resume),
                stop,
                slice_days,
                dry_run,
                transform,
            )

    return imported


async def _resume_start(
    storage: StorageService, measurement: str, start: datetime, resume: bool
) -> datetime:
    if not resume:
        return start

    cursor = await storage.read_meta(f"{CURSOR_KEY_PREFIX}:{measurement}")
    if cursor is None:
        return start

    logger.info(f"Resuming import of {measurement} at {cursor}")

    return datetime.fromisoformat(cursor)


async def _import_measurement(
    storage: StorageService,
    session: aiohttp.ClientSession,
    credentials: InfluxCredentials,
    measurement: str,
    start: datetime,
    stop: datetime,
    slice_days: int,
    dry_run: bool,
    transform: PointTransform | None,
) -> int:
    imported = 0
    slice_start = start

    while slice_start < stop:
        slice_stop = min(slice_start + timedelta(days=slice_days), stop)

        payload = await query_influxdb(
            session, credentials, measurement, slice_start, slice_stop
        )
        points = _transform(list(parse_annotated_csv(payload)), transform)

        if points and not dry_run:
            await storage.write_points(points)
            await storage.write_meta(
                f"{CURSOR_KEY_PREFIX}:{measurement}", slice_stop.isoformat()
            )

        values = _written_values(points)
        imported += values
        logger.info(
            f"Imported {values} values of {measurement} "
            f"from {slice_start.date()} to {slice_stop.date()}"
        )

        slice_start = slice_stop

    return imported


async def consolidate_modules(storage: StorageService) -> int:
    """Fold the historic module tag shapes onto the one written today.

    The monitoring API changed what it reports as ``identifier``, and the
    naming of an optimizer changed with it, so an imported history holds the
    same physical module under several tag sets. The serial number stayed the
    same throughout, so the series carrying the newest point wins and the
    older ones are merged into it.

    Doing nothing is an option -- no query reads ``modules`` back -- but it
    would leave every dashboard to sort the shapes out by hand, forever.
    """
    plan = await storage.fetch_all(MODULE_SERIES_MERGE_PLAN)
    if not plan:
        return 0

    for row in plan:
        source_id = int(row["source_id"])
        await storage.execute_write(
            MERGE_SERIES_POINTS,
            {"source_id": source_id, "target_id": int(row["target_id"])},
        )
        await storage.execute_write(DELETE_SERIES, {"series_id": source_id})

    storage.forget_series_cache()

    logger.info(f"Consolidated {len(plan)} legacy module series")

    return len(plan)
