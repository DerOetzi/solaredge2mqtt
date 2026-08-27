"""Tests for the InfluxDB migration command line tool."""

import argparse
from datetime import datetime, timezone

import pytest

from migrate_influxdb import (
    _measurement_list,
    _parse_time,
    build_credentials,
    read_legacy_influxdb_section,
    training_point_to_canonical,
)
from solaredge2mqtt.core.exceptions import ConfigurationException
from solaredge2mqtt.core.storage import Point

LEGACY_CONFIGURATION = """
modbus:
  host: 192.168.1.100
influxdb:
  host: http://influx.local
  port: 8086
  token: !secret influxdb_token
  org: test_org
  bucket: solaredge
"""


def write_legacy(tmp_path, content=LEGACY_CONFIGURATION, secrets=True):
    """Write a configuration that still carries the influxdb section."""
    (tmp_path / "configuration.yml").write_text(content)
    if secrets:
        (tmp_path / "secrets.yml").write_text("influxdb_token: token_123\n")
    return str(tmp_path)


def arguments(config_dir, **overrides):
    """Build the argument namespace the tool works with."""
    values = {
        "config_dir": config_dir,
        "url": None,
        "token": None,
        "org": None,
        "bucket": None,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


class TestReadLegacySection:
    """Tests for reading the configuration that is about to be replaced."""

    def test_resolves_the_token_secret(self, tmp_path):
        """The token lives in secrets.yml, not in the configuration."""
        section = read_legacy_influxdb_section(write_legacy(tmp_path))

        assert section["token"] == "token_123"

    def test_missing_file_yields_nothing(self, tmp_path):
        """Without a configuration the credentials have to be given as flags."""
        assert read_legacy_influxdb_section(str(tmp_path)) == {}

    def test_upgraded_configuration_yields_nothing(self, tmp_path):
        """After the upgrade the section is gone, the flags take over."""
        config_dir = write_legacy(tmp_path, "modbus:\n  host: 192.168.1.100\n")

        assert read_legacy_influxdb_section(config_dir) == {}

    def test_missing_secrets_file_keeps_the_reference(self, tmp_path):
        """A broken secret must not crash the tool before it reports."""
        config_dir = write_legacy(tmp_path, secrets=False)

        assert read_legacy_influxdb_section(config_dir)["token"] is None

    def test_ignores_a_backup(self, tmp_path):
        """Which backup is the right one is not for the tool to guess."""
        config_dir = write_legacy(tmp_path, "modbus:\n  host: 192.168.1.100\n")
        (tmp_path / "configuration.yml.backup.20260101120000").write_text(
            LEGACY_CONFIGURATION
        )

        assert read_legacy_influxdb_section(config_dir) == {}


class TestBuildCredentials:
    """Tests for combining the credential sources."""

    def test_reads_the_legacy_section(self, tmp_path):
        """The old configuration is the primary source."""
        credentials = build_credentials(arguments(write_legacy(tmp_path)))

        assert credentials.url == "http://influx.local:8086"
        assert credentials.token == "token_123"
        assert credentials.org == "test_org"
        assert credentials.bucket == "solaredge"

    def test_flags_win(self, tmp_path):
        """Explicit flags override an existing configuration."""
        credentials = build_credentials(
            arguments(
                write_legacy(tmp_path),
                url="http://other:8086",
                token="flag_token",
                org="flag_org",
                bucket="flag_bucket",
            )
        )

        assert credentials.url == "http://other:8086"
        assert credentials.token == "flag_token"
        assert credentials.org == "flag_org"
        assert credentials.bucket == "flag_bucket"

    def test_adds_https_for_a_bare_host(self, tmp_path):
        """A host without a scheme is treated as https, as the settings did."""
        config_dir = write_legacy(
            tmp_path,
            "influxdb:\n  host: influx.local\n  port: 8086\n  org: o\n",
            secrets=False,
        )

        credentials = build_credentials(arguments(config_dir))

        assert credentials.url == "https://influx.local:8086"

    def test_completes_a_bare_flag_url(self, tmp_path):
        """A host given without a scheme is completed, not passed on broken."""
        credentials = build_credentials(
            arguments(write_legacy(tmp_path), url="influx.local")
        )

        assert credentials.url == "https://influx.local:8086"

    def test_requires_a_host(self, tmp_path):
        """Without a host there is nothing to import from."""
        config_dir = write_legacy(tmp_path, "modbus:\n  host: 192.168.1.100\n")

        with pytest.raises(ConfigurationException) as error:
            build_credentials(arguments(config_dir))

        assert "--url" in error.value.message
        assert "backup" in error.value.message


class TestArgumentHelpers:
    """Tests for the argument conversions."""

    def test_parses_an_iso_timestamp_as_utc(self):
        """A naive timestamp is read as UTC, matching the stored values."""
        assert _parse_time("2024-01-01T00:00:00", datetime.now(tz=timezone.utc)) == (
            datetime(2024, 1, 1, tzinfo=timezone.utc)
        )

    def test_keeps_an_explicit_offset(self):
        """An offset in the argument is honoured."""
        parsed = _parse_time("2024-01-01T01:00:00+01:00", datetime.now(tz=timezone.utc))

        assert parsed == datetime(2024, 1, 1, tzinfo=timezone.utc)

    def test_falls_back_to_the_default(self):
        """Without an argument the caller's default applies."""
        default = datetime(2020, 1, 1, tzinfo=timezone.utc)

        assert _parse_time(None, default) == default

    def test_splits_a_measurement_list(self):
        """The measurements are given as a comma separated list."""
        assert _measurement_list("energy, forecast ,") == ["energy", "forecast"]


def training_point() -> Point:
    """A stored snapshot as releases before the local storage wrote it."""
    point = Point("forecast_training").time(
        datetime(2024, 1, 1, 11, 0, tzinfo=timezone.utc)
    )
    point.field("temp", 12.5).field("clouds", 40).field("weather_id", 803)
    point.field("weather_main", "Clouds").field("energy", 1200.0).field("power", 1200)
    return point


class TestTrainingPointToCanonical:
    """Tests for converting the stored schema during the migration."""

    def test_renames_the_weather_fields(self):
        """The storage holds pvlearn's names after the migration."""
        converted = training_point_to_canonical(training_point())

        assert converted is not None
        assert converted.fields["temperature"] == pytest.approx(12.5)
        assert converted.fields["cloud_cover"] == 40

    def test_translates_the_condition_once(self):
        """The WMO translation moves from every read to this single conversion."""
        converted = training_point_to_canonical(training_point())

        assert converted is not None
        assert converted.fields["condition_code"] == 3

    def test_drops_fields_without_a_canonical_counterpart(self):
        """weather_main is not a pvlearn feature and is not carried over."""
        converted = training_point_to_canonical(training_point())

        assert converted is not None
        assert "weather_main" not in converted.fields
        assert "temp" not in converted.fields

    def test_keeps_the_target_and_the_deprecated_power(self):
        """Both live next to the weather features, under their own names."""
        converted = training_point_to_canonical(training_point())

        assert converted is not None
        assert converted.fields["energy"] == pytest.approx(1200.0)
        assert converted.fields["power"] == 1200

    def test_stamps_the_provider(self):
        """Every migrated row states which provider wrote it."""
        converted = training_point_to_canonical(training_point())

        assert converted is not None
        assert converted.fields["weather_provider"] == "openweathermap"

    def test_keeps_the_timestamp(self):
        """The snapshot stays on the hour it belongs to."""
        converted = training_point_to_canonical(training_point())

        assert converted is not None
        assert converted.timestamp == datetime(2024, 1, 1, 11, 0, tzinfo=timezone.utc)

    def test_drops_a_snapshot_without_usable_fields(self):
        """A row of nothing but dropped fields carries no provider stamp either."""
        point = Point("forecast_training").field("weather_main", "Clouds")

        assert training_point_to_canonical(point) is None

    def test_leaves_other_measurements_untouched(self):
        """Only forecast_training changed its schema."""
        point = Point("energy").field("pv_production", 3.5)

        assert training_point_to_canonical(point) is point
