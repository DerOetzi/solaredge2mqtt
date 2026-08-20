"""Tests for the versioned configuration upgrades."""

from pathlib import Path

import pytest
import yaml
from loguru import logger as loguru_logger

from solaredge2mqtt.core.settings.loader import ConfigurationLoader
from solaredge2mqtt.core.settings.upgrades import (
    CONFIG_VERSION,
    CONFIG_VERSION_KEY,
    TOKEN_PLACEHOLDER,
    RawConfigLoader,
    influx_url,
    migration_command,
    upgrade_configuration,
)

INFLUXDB_CONFIGURATION = """
modbus:
  host: 192.168.1.100
mqtt:
  broker: mqtt.example.com
influxdb:
  host: http://localhost
  port: 8086
  token: !secret influxdb_token
  org: test_org
  bucket: solaredge
  retention_raw: 12
  debounce_cycles: 7
"""


def write_configuration(tmp_path: Path, content: str) -> str:
    """Write a configuration file and return its path."""
    config_file = tmp_path / "configuration.yml"
    config_file.write_text(content)
    (tmp_path / "secrets.yml").write_text("influxdb_token: test_token\n")
    return str(config_file)


def read_raw(config_file: str) -> dict:
    """Read a configuration file without resolving its secrets."""
    with open(config_file, "r", encoding="utf-8") as file:
        return yaml.load(file, Loader=RawConfigLoader)


class TestInfluxdbUpgrade:
    """Tests for replacing the influxdb section with storage."""

    def test_removes_the_influxdb_section(self, tmp_path):
        """Pydantic would drop the unknown section silently otherwise."""
        config_file = write_configuration(tmp_path, INFLUXDB_CONFIGURATION)

        assert upgrade_configuration(config_file) is True
        assert "influxdb" not in read_raw(config_file)

    def test_carries_the_tuned_values_over(self, tmp_path):
        """A tuned raw retention must survive the upgrade."""
        config_file = write_configuration(tmp_path, INFLUXDB_CONFIGURATION)

        upgrade_configuration(config_file)
        storage = read_raw(config_file)["storage"]

        assert storage["retention_raw"] == 12
        assert storage["debounce_cycles"] == 7
        assert storage["enable"] is True

    def test_does_not_carry_the_bucket_retention(self, tmp_path):
        """Locally the history is kept, the bucket expiry was an artefact."""
        config_file = write_configuration(tmp_path, INFLUXDB_CONFIGURATION)

        upgrade_configuration(config_file)

        assert "retention" not in read_raw(config_file)["storage"]

    def test_keeps_existing_storage_values(self, tmp_path):
        """An already configured storage section wins over the old values."""
        config_file = write_configuration(
            tmp_path, INFLUXDB_CONFIGURATION + "storage:\n  retention_raw: 48\n"
        )

        upgrade_configuration(config_file)

        assert read_raw(config_file)["storage"]["retention_raw"] == 48

    def test_writes_a_backup(self, tmp_path):
        """The previous file stays available if the upgrade goes wrong."""
        config_file = write_configuration(tmp_path, INFLUXDB_CONFIGURATION)

        upgrade_configuration(config_file)

        assert list(tmp_path.glob("configuration.yml.backup.*"))

    def test_preserves_other_secrets(self, tmp_path):
        """Rewriting must not resolve a secret into the configuration file."""
        config_file = write_configuration(
            tmp_path,
            INFLUXDB_CONFIGURATION + "monitoring:\n  password: !secret mqtt_password\n",
        )

        upgrade_configuration(config_file)

        assert "!secret mqtt_password" in Path(config_file).read_text()


class TestMigrationCommand:
    """Tests for the import command the upgrade spells out."""

    SECTION = {
        "host": "http://localhost",
        "port": 8086,
        "org": "test_org",
        "bucket": "solaredge",
        "token": "super_secret",
    }

    def test_names_every_connection_value(self):
        """The removed section is the only place these are written down."""
        command = migration_command(self.SECTION, "config")

        assert command == (
            "solaredge2mqtt-migrate-influxdb --config-dir config "
            "--url http://localhost:8086 --org test_org --bucket solaredge "
            f"--token {TOKEN_PLACEHOLDER}"
        )

    def test_never_reveals_the_token(self):
        """A token in the service log is a token in every log shipped from it."""
        command = migration_command(self.SECTION, "config")

        assert "super_secret" not in command

    def test_skips_what_the_section_does_not_hold(self):
        """A partial section still yields a command worth starting from."""
        command = migration_command({"host": "influx.local"}, "config")

        assert command == (
            "solaredge2mqtt-migrate-influxdb --config-dir config "
            f"--url https://influx.local:8086 --token {TOKEN_PLACEHOLDER}"
        )

    def test_is_logged_before_the_file_is_rewritten(self, tmp_path):
        """Reading the file at log time proves the section is still there."""
        config_file = write_configuration(tmp_path, INFLUXDB_CONFIGURATION)
        seen = []

        def sink(message):
            text = str(message)
            if "--url" in text:
                seen.append((text, read_raw(config_file)))

        sink_id = loguru_logger.add(sink, level=0)
        try:
            upgrade_configuration(config_file)
        finally:
            loguru_logger.remove(sink_id)

        ((logged, config_while_logging),) = seen

        assert "--url http://localhost:8086" in logged
        assert "--org test_org" in logged
        assert "test_token" not in logged
        assert "influxdb" in config_while_logging
        assert "influxdb" not in read_raw(config_file)


class TestInfluxUrl:
    """Tests for building the base URL of an InfluxDB."""

    def test_keeps_an_explicit_scheme_and_port(self):
        """A complete URL is passed through untouched."""
        assert influx_url("http://influx.local:8086") == "http://influx.local:8086"

    def test_assumes_https_and_the_default_port(self):
        """A bare host is completed the way the removed settings did."""
        assert influx_url("influx.local") == "https://influx.local:8086"

    def test_uses_the_configured_port(self):
        """A port next to the host in the section is honoured."""
        assert influx_url("influx.local", 9999) == "https://influx.local:9999"


class TestUpgradeVersioning:
    """Tests for the version bookkeeping."""

    def test_records_the_version(self, tmp_path):
        """The version marks the file as upgraded."""
        config_file = write_configuration(tmp_path, INFLUXDB_CONFIGURATION)

        upgrade_configuration(config_file)

        assert read_raw(config_file)[CONFIG_VERSION_KEY] == CONFIG_VERSION

    def test_comments_are_lost_on_a_migrated_file(self, tmp_path):
        """Documented consequence of round-tripping the file through yaml."""
        config_file = write_configuration(
            tmp_path, "# my inverter\n" + INFLUXDB_CONFIGURATION
        )

        upgrade_configuration(config_file)

        assert "# my inverter" not in Path(config_file).read_text()
        assert (
            "# my inverter"
            in next(tmp_path.glob("configuration.yml.backup.*")).read_text()
        )

    def test_is_idempotent(self, tmp_path):
        """A second start must not rewrite the file again."""
        config_file = write_configuration(tmp_path, INFLUXDB_CONFIGURATION)
        upgrade_configuration(config_file)
        content = Path(config_file).read_text()

        assert upgrade_configuration(config_file) is False
        assert Path(config_file).read_text() == content

    def test_leaves_a_configuration_without_influxdb_alone(self, tmp_path):
        """Nothing to migrate means no rewrite, so comments survive."""
        content = (
            "# the inverter\nmodbus:\n  host: 192.168.1.100\nmqtt:\n  broker: broker\n"
        )
        config_file = write_configuration(tmp_path, content)

        assert upgrade_configuration(config_file) is False
        assert Path(config_file).read_text() == content
        assert not list(tmp_path.glob("configuration.yml.backup.*"))


class TestLoaderIntegration:
    """Tests for the upgrade running as part of loading the configuration."""

    def test_loading_upgrades_and_applies_the_values(self, tmp_path):
        """The service starts on an old configuration without manual work."""
        write_configuration(tmp_path, INFLUXDB_CONFIGURATION)

        settings = ConfigurationLoader.load_configuration(str(tmp_path))

        assert settings.storage.retention_raw == 12
        assert settings.storage.debounce_cycles == 7

    def test_loading_a_missing_secret_still_fails(self, tmp_path):
        """The upgrade must not swallow a broken secret reference."""
        config_file = tmp_path / "configuration.yml"
        config_file.write_text(
            "modbus:\n  host: 192.168.1.100\nmqtt:\n"
            "  broker: broker\n  password: !secret missing\n"
        )
        (tmp_path / "secrets.yml").write_text("other: value\n")

        with pytest.raises(ValueError):
            ConfigurationLoader.load_configuration(str(tmp_path))
