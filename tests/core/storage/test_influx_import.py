"""Tests for the one-off InfluxDB import."""

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from solaredge2mqtt.core.exceptions import ConfigurationException
from solaredge2mqtt.core.storage import Point
from solaredge2mqtt.core.storage.influx_import import (
    CURSOR_KEY_PREFIX,
    DEFAULT_MEASUREMENTS,
    RAW_MEASUREMENTS,
    InfluxCredentials,
    consolidate_modules,
    import_from_influxdb,
    import_from_line_protocol,
    measurements_to_import,
    parse_annotated_csv,
    parse_line_protocol,
)

FIXTURES = Path(__file__).parent.parent.parent / "fixtures"

CREDENTIALS = InfluxCredentials("http://influx:8086", "token", "org", "solaredge")

START = datetime(2024, 1, 1, tzinfo=timezone.utc)
STOP = datetime(2024, 1, 2, tzinfo=timezone.utc)


def csv_session(payloads):
    """Build a session whose post returns the given payloads in order."""
    responses = list(payloads)

    def post(*args, **kwargs):
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.text = AsyncMock(return_value=responses.pop(0))
        context = MagicMock()
        context.__aenter__ = AsyncMock(return_value=response)
        context.__aexit__ = AsyncMock(return_value=False)
        return context

    session = MagicMock()
    session.post = post
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)

    return session


class TestAnnotatedCsv:
    """Tests for parsing the annotated CSV of the query API."""

    def test_reads_every_row(self):
        """Both tables of the export become points."""
        payload = (FIXTURES / "influx_export.csv").read_text()

        points = list(parse_annotated_csv(payload))

        assert len(points) == 5

    def test_casts_values_by_datatype(self):
        """A double stays a float, a string stays a string."""
        payload = (FIXTURES / "influx_export.csv").read_text()

        points = list(parse_annotated_csv(payload))

        assert points[0].fields == {"pv_production": 3.5}
        assert points[4].fields == {"weather_main": "Clouds"}

    def test_reads_the_timestamp(self):
        """The point keeps the timestamp it had in InfluxDB."""
        payload = (FIXTURES / "influx_export.csv").read_text()

        points = list(parse_annotated_csv(payload))

        assert points[0].timestamp == datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)

    def test_reads_tags(self):
        """Every column outside the reserved set is a tag."""
        payload = (FIXTURES / "influx_export.csv").read_text()

        points = list(parse_annotated_csv(payload))

        assert points[0].tags == {"unit": "cumulated"}

    def test_skips_empty_tag_values(self):
        """Flux emits an empty column for an absent tag."""
        payload = (FIXTURES / "influx_export.csv").read_text()

        points = list(parse_annotated_csv(payload))

        assert points[2].tags == {}

    def test_keeps_the_datatypes_across_continuation_blocks(self):
        """A large answer repeats the header alone, without the annotations.

        Dropping the datatypes there turned every column into a string, so the
        timestamp of every continuation row stopped being a datetime.
        """
        payload = (FIXTURES / "influx_export.csv").read_text()

        points = list(parse_annotated_csv(payload))

        assert points[3].fields == {"pv_production": 5.5}
        assert points[3].timestamp == datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
        assert points[3].tags == {"unit": "cumulated"}

    def test_casts_boolean_values(self):
        """A boolean column of the query API is not a string.

        Keeping it a string would store "false" as a truthy value.
        """
        payload = (
            "#datatype,string,long,dateTime:RFC3339,boolean,string,string\n"
            ",result,table,_time,_value,_field,_measurement\n"
            ",,0,2024-01-01T10:00:00Z,true,charging,wallbox\n"
            ",,0,2024-01-01T11:00:00Z,FALSE,charging,wallbox\n"
        )

        points = list(parse_annotated_csv(payload))

        assert [point.fields for point in points] == [
            {"charging": True},
            {"charging": False},
        ]

    def test_parses_a_timestamp_left_as_a_string(self):
        """An export without the dateTime annotation still carries RFC3339."""
        payload = (
            "#datatype,string,long,string,double,string,string\n"
            ",result,table,_time,_value,_field,_measurement\n"
            ",,0,2024-01-01T10:00:00Z,3.5,pv_production,energy\n"
        )

        points = list(parse_annotated_csv(payload))

        assert points[0].timestamp == datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)

    def test_ignores_rows_without_a_value(self):
        """A row without measurement, field or value carries nothing."""
        payload = (
            "#datatype,string,long,dateTime:RFC3339,double,string,string\n"
            ",result,table,_time,_value,_field,_measurement\n"
            ",,0,2024-01-01T10:00:00Z,,pv_production,energy\n"
        )

        assert list(parse_annotated_csv(payload)) == []


class TestLineProtocol:
    """Tests for parsing a line protocol dump."""

    def test_reads_every_line(self):
        """Comments and blank lines are skipped."""
        payload = (FIXTURES / "influx_export.lp").read_text()

        points = list(parse_line_protocol(payload))

        assert len(points) == 4

    def test_reads_tags_and_fields(self):
        """A line carries its tag set and all of its fields."""
        payload = (FIXTURES / "influx_export.lp").read_text()

        points = list(parse_line_protocol(payload))

        assert points[1].tags == {"unit": "cumulated"}
        assert points[1].fields == {"pv_production": 4.5, "grid_delivery": 1.5}

    def test_keeps_integer_fields_integer(self):
        """The trailing i marks an integer field, floats would change the type."""
        payload = (FIXTURES / "influx_export.lp").read_text()

        points = list(parse_line_protocol(payload))

        assert points[2].fields["power"] == 2500
        assert isinstance(points[2].fields["power"], int)

    def test_reads_quoted_strings(self):
        """String fields are quoted in line protocol."""
        payload = (FIXTURES / "influx_export.lp").read_text()

        points = list(parse_line_protocol(payload))

        assert points[3].fields["weather_main"] == "Clouds"

    def test_reads_nanosecond_timestamps(self):
        """InfluxDB stored nanoseconds, the storage keeps seconds."""
        payload = (FIXTURES / "influx_export.lp").read_text()

        points = list(parse_line_protocol(payload))

        assert points[0].epoch_seconds() == 1704106800

    def test_reads_boolean_fields(self):
        """Boolean fields use the short spellings of line protocol."""
        points = list(parse_line_protocol("m flag=t 1704106800000000000"))

        assert points[0].fields == {"flag": True}

    def test_reads_false_boolean_fields(self):
        """The false spellings must not fall through to the float branch."""
        points = list(parse_line_protocol("m flag=f 1704106800000000000"))

        assert points[0].fields == {"flag": False}

    def test_handles_escaped_separators(self):
        """A tag value may contain an escaped comma or space."""
        points = list(parse_line_protocol("m,name=Module\\ 1 power=1.0"))

        assert points[0].tags == {"name": "Module 1"}

    def test_skips_incomplete_lines(self):
        """A line without a field set carries nothing."""
        assert list(parse_line_protocol("measurement_only")) == []


class TestMeasurementSelection:
    """Tests for choosing what to import."""

    def test_defaults_exclude_the_raw_samples(self):
        """Raw samples are at most a day old and dominate the row count."""
        assert measurements_to_import(None, False) == list(DEFAULT_MEASUREMENTS)

    def test_raw_samples_are_opt_in(self):
        """They can still be imported on request."""
        selected = measurements_to_import(None, True)

        assert set(RAW_MEASUREMENTS) <= set(selected)

    def test_explicit_list_wins(self):
        """An explicit selection overrides both defaults."""
        assert measurements_to_import(["energy"], True) == ["energy"]


class TestImportFromLineProtocol:
    """Tests for importing a dump into the storage."""

    @pytest.mark.asyncio
    async def test_writes_the_points(self, storage):
        """The imported history is queryable afterwards."""
        imported = await import_from_line_protocol(
            storage, FIXTURES / "influx_export.lp"
        )

        rows = await storage.fetch_all("SELECT COUNT(*) FROM point")

        assert imported == 11
        assert rows[0][0] == 11

    @pytest.mark.asyncio
    async def test_is_idempotent(self, storage):
        """Running the import twice must not duplicate a single row."""
        await import_from_line_protocol(storage, FIXTURES / "influx_export.lp")
        await import_from_line_protocol(storage, FIXTURES / "influx_export.lp")

        rows = await storage.fetch_all("SELECT COUNT(*) FROM point")

        assert rows[0][0] == 11

    @pytest.mark.asyncio
    async def test_reads_a_directory(self, storage):
        """A dump may be split across several files."""
        imported = await import_from_line_protocol(storage, FIXTURES)

        assert imported == 11

    @pytest.mark.asyncio
    async def test_applies_the_transform(self, storage):
        """The migration converts the stored schema through this hook."""

        def rename(point):
            renamed = Point(point.measurement)
            renamed.timestamp = point.timestamp
            for field, value in point.fields.items():
                renamed.field(f"canonical_{field}", value)
            return renamed

        await import_from_line_protocol(
            storage, FIXTURES / "influx_export.lp", transform=rename
        )

        rows = await storage.fetch_all("SELECT DISTINCT field FROM series")

        assert all(str(row["field"]).startswith("canonical_") for row in rows)

    @pytest.mark.asyncio
    async def test_transform_may_drop_a_point(self, storage):
        """Returning None removes a point that carries nothing worth keeping."""
        imported = await import_from_line_protocol(
            storage, FIXTURES / "influx_export.lp", transform=lambda point: None
        )

        rows = await storage.fetch_all("SELECT COUNT(*) FROM point")

        assert imported == 0
        assert rows[0][0] == 0

    @pytest.mark.asyncio
    async def test_dry_run_writes_nothing(self, storage):
        """The dry run reports the volume without touching the database."""
        imported = await import_from_line_protocol(
            storage, FIXTURES / "influx_export.lp", dry_run=True
        )

        rows = await storage.fetch_all("SELECT COUNT(*) FROM point")

        assert imported == 11
        assert rows[0][0] == 0

    @pytest.mark.asyncio
    async def test_counts_a_repeated_stamp_once(self, storage):
        """Stamping every record of an hour still writes a single row."""

        def stamp(point):
            return point.field("weather_provider", "openweathermap")

        imported = await import_from_line_protocol(
            storage, FIXTURES / "influx_export.lp", transform=stamp
        )

        rows = await storage.fetch_all("SELECT COUNT(*) FROM point")

        assert imported == rows[0][0]

    @pytest.mark.asyncio
    async def test_counts_the_fields_a_transform_adds(self, storage):
        """A transform that stamps a field writes -- and reports -- more rows."""

        def stamp(point):
            return point.field("weather_provider", "openweathermap")

        imported = await import_from_line_protocol(
            storage, FIXTURES / "influx_export.lp", transform=stamp
        )

        rows = await storage.fetch_all("SELECT COUNT(*) FROM point")

        assert imported == 15
        assert rows[0][0] == 15


class TestImportFromInfluxdb:
    """Tests for importing over the query API."""

    @pytest.mark.asyncio
    async def test_imports_a_measurement(self, storage):
        """The parsed rows are written into the storage."""
        payload = (FIXTURES / "influx_export.csv").read_text()

        with patch("aiohttp.ClientSession", return_value=csv_session([payload])):
            imported = await import_from_influxdb(
                storage, CREDENTIALS, START, STOP, ["energy"]
            )

        assert imported == 5

    @pytest.mark.asyncio
    async def test_slices_the_range(self, storage):
        """Long histories are queried day by day."""
        payloads = ["", ""]

        with patch("aiohttp.ClientSession", return_value=csv_session(payloads)):
            imported = await import_from_influxdb(
                storage,
                CREDENTIALS,
                START,
                datetime(2024, 1, 3, tzinfo=timezone.utc),
                ["energy"],
            )

        assert imported == 0

    @pytest.mark.asyncio
    async def test_applies_the_transform(self, storage):
        """The query API import converts the schema through the same hook."""
        payload = (FIXTURES / "influx_export.csv").read_text()

        with patch("aiohttp.ClientSession", return_value=csv_session([payload])):
            imported = await import_from_influxdb(
                storage,
                CREDENTIALS,
                START,
                STOP,
                ["energy"],
                transform=lambda point: None,
            )

        assert imported == 0

    @pytest.mark.asyncio
    async def test_records_a_resume_cursor(self, storage):
        """An interrupted import continues where it stopped."""
        payload = (FIXTURES / "influx_export.csv").read_text()

        with patch("aiohttp.ClientSession", return_value=csv_session([payload])):
            await import_from_influxdb(storage, CREDENTIALS, START, STOP, ["energy"])

        assert await storage.read_meta(f"{CURSOR_KEY_PREFIX}:energy") is not None

    @pytest.mark.asyncio
    async def test_resume_starts_at_the_cursor(self, storage):
        """Resuming skips the slices that were already imported."""
        await storage.write_meta(f"{CURSOR_KEY_PREFIX}:energy", STOP.isoformat())

        with patch("aiohttp.ClientSession", return_value=csv_session([])):
            imported = await import_from_influxdb(
                storage, CREDENTIALS, START, STOP, ["energy"], resume=True
            )

        assert imported == 0

    @pytest.mark.asyncio
    async def test_resume_without_a_cursor_starts_at_the_beginning(self, storage):
        """The first run of a resumable import has nothing to resume from."""
        payload = (FIXTURES / "influx_export.csv").read_text()

        with patch("aiohttp.ClientSession", return_value=csv_session([payload])):
            imported = await import_from_influxdb(
                storage, CREDENTIALS, START, STOP, ["energy"], resume=True
            )

        assert imported == 5

    @pytest.mark.asyncio
    async def test_requires_credentials(self, storage):
        """Without a token the query API would answer with an error page."""
        credentials = InfluxCredentials("http://influx:8086", "", "", "solaredge")

        with pytest.raises(ConfigurationException):
            await import_from_influxdb(storage, credentials, START, STOP, ["energy"])


SERIAL = "15FE5405-6C"

#: The tag shape a release before the monitoring API change wrote.
LEGACY_MODULE = {
    "serialnumber": SERIAL,
    "identifier": "254651790",
    "name": "Module 1.4.8",
}

#: The shape written for a single day while the naming was still wrong.
INTERIM_MODULE = {
    "serialnumber": SERIAL,
    "identifier": "15FE5405",
    "name": "Optimizer 1.4.8",
}

#: The shape the running release writes.
CURRENT_MODULE = {
    "serialnumber": SERIAL,
    "identifier": "15FE5405",
    "name": "Module 1.4.8",
}

MODULE_HOURS = [datetime(2026, 8, day, 11, tzinfo=timezone.utc) for day in (1, 3, 5)]


class TestConsolidateModules:
    """Tests for folding the historic module tag shapes onto the current one."""

    @pytest.fixture
    def module_series(self, seed):
        """Provide a helper seeding one module shape at the given hours."""

        async def _seed(tags, samples):
            await seed("modules", "power", tags, samples)

        return _seed

    async def module_tags(self, storage):
        rows = await storage.fetch_all(
            "SELECT tag_key, tag_value FROM series_tag WHERE series_id IN "
            "(SELECT series_id FROM series WHERE measurement = 'modules')"
        )
        return {(str(row["tag_key"]), str(row["tag_value"])) for row in rows}

    @pytest.mark.asyncio
    async def test_merges_the_legacy_shapes(self, storage, module_series):
        """The same module under three tag sets becomes one series."""
        await module_series(LEGACY_MODULE, [(MODULE_HOURS[0], 100.0)])
        await module_series(INTERIM_MODULE, [(MODULE_HOURS[1], 200.0)])
        await module_series(CURRENT_MODULE, [(MODULE_HOURS[2], 300.0)])

        merged = await consolidate_modules(storage)

        series = await storage.fetch_all(
            "SELECT COUNT(*) FROM series WHERE measurement = 'modules'"
        )
        points = await storage.fetch_all("SELECT ts, value FROM point ORDER BY ts")

        assert merged == 2
        assert series[0][0] == 1
        assert [row["value"] for row in points] == [100.0, 200.0, 300.0]

    @pytest.mark.asyncio
    async def test_keeps_the_tags_of_the_newest_series(self, storage, module_series):
        """The shape the running release writes is the one that survives."""
        await module_series(LEGACY_MODULE, [(MODULE_HOURS[0], 100.0)])
        await module_series(CURRENT_MODULE, [(MODULE_HOURS[2], 300.0)])

        await consolidate_modules(storage)

        assert await self.module_tags(storage) == {
            ("serialnumber", SERIAL),
            ("identifier", "15FE5405"),
            ("name", "Module 1.4.8"),
        }

    @pytest.mark.asyncio
    async def test_the_newest_series_wins_a_collision(self, storage, module_series):
        """The older shape may hold an incomplete snapshot of the same hour."""
        await module_series(CURRENT_MODULE, [(MODULE_HOURS[1], 267.0)])
        await module_series(INTERIM_MODULE, [(MODULE_HOURS[1], 0.0)])
        await module_series(CURRENT_MODULE, [(MODULE_HOURS[2], 300.0)])

        await consolidate_modules(storage)

        points = await storage.fetch_all("SELECT ts, value FROM point ORDER BY ts")

        assert [row["value"] for row in points] == [267.0, 300.0]

    @pytest.mark.asyncio
    async def test_keeps_different_modules_apart(self, storage, module_series):
        """The serial number is what identifies a module, not its name."""
        await module_series(LEGACY_MODULE, [(MODULE_HOURS[0], 100.0)])
        await module_series(
            {**CURRENT_MODULE, "serialnumber": "178A16D7-8E", "identifier": "178A16D7"},
            [(MODULE_HOURS[2], 300.0)],
        )

        merged = await consolidate_modules(storage)

        series = await storage.fetch_all(
            "SELECT COUNT(*) FROM series WHERE measurement = 'modules'"
        )

        assert merged == 0
        assert series[0][0] == 2

    @pytest.mark.asyncio
    async def test_leaves_a_module_without_a_serial_alone(self, storage, module_series):
        """Without the stable key there is nothing to merge onto."""
        await module_series({"identifier": "254651790"}, [(MODULE_HOURS[0], 100.0)])
        await module_series({"identifier": "15FE5405"}, [(MODULE_HOURS[2], 300.0)])

        merged = await consolidate_modules(storage)

        series = await storage.fetch_all(
            "SELECT COUNT(*) FROM series WHERE measurement = 'modules'"
        )

        assert merged == 0
        assert series[0][0] == 2

    @pytest.mark.asyncio
    async def test_is_idempotent(self, storage, module_series):
        """A second run finds nothing left to merge."""
        await module_series(LEGACY_MODULE, [(MODULE_HOURS[0], 100.0)])
        await module_series(CURRENT_MODULE, [(MODULE_HOURS[2], 300.0)])

        await consolidate_modules(storage)

        assert await consolidate_modules(storage) == 0

    @pytest.mark.asyncio
    async def test_forgets_the_merged_series(self, storage, module_series):
        """A write after the merge must not reuse a deleted series id."""
        await module_series(LEGACY_MODULE, [(MODULE_HOURS[0], 100.0)])
        await module_series(CURRENT_MODULE, [(MODULE_HOURS[2], 300.0)])

        await consolidate_modules(storage)
        await module_series(LEGACY_MODULE, [(MODULE_HOURS[1], 200.0)])

        points = await storage.fetch_all("SELECT ts, value FROM point ORDER BY ts")

        assert [row["value"] for row in points] == [100.0, 200.0, 300.0]

    @pytest.mark.asyncio
    async def test_does_nothing_without_modules(self, storage):
        """An installation without the monitoring service is untouched."""
        assert await consolidate_modules(storage) == 0
