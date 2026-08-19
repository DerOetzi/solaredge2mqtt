"""Tests for the versioned configuration upgrades."""

from pathlib import Path

import pytest
import yaml

from solaredge2mqtt.core.settings.loader import ConfigurationLoader
from solaredge2mqtt.core.settings.upgrades import (
    CONFIG_VERSION,
    CONFIG_VERSION_KEY,
    RawConfigLoader,
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


class TestUpgradeVersioning:
    """Tests for the version bookkeeping."""

    def test_records_the_version(self, tmp_path):
        """The version marks the file as upgraded."""
        config_file = write_configuration(tmp_path, INFLUXDB_CONFIGURATION)

        upgrade_configuration(config_file)

        assert read_raw(config_file)[CONFIG_VERSION_KEY] == CONFIG_VERSION

    def test_is_idempotent(self, tmp_path):
        """A second start must not rewrite the file again."""
        config_file = write_configuration(tmp_path, INFLUXDB_CONFIGURATION)
        upgrade_configuration(config_file)
        content = Path(config_file).read_text()

        assert upgrade_configuration(config_file) is False
        assert Path(config_file).read_text() == content

    def test_upgrades_a_configuration_without_influxdb(self, tmp_path):
        """A file without the old section is only stamped with the version."""
        config_file = write_configuration(
            tmp_path, "modbus:\n  host: 192.168.1.100\nmqtt:\n  broker: broker\n"
        )

        assert upgrade_configuration(config_file) is True
        assert read_raw(config_file)[CONFIG_VERSION_KEY] == CONFIG_VERSION


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
