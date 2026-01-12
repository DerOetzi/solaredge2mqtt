"""Tests for configuration migrator module."""

import tempfile
from pathlib import Path
from typing import Any

import yaml

from solaredge2mqtt.core.settings.migrator import ConfigurationMigrator
from solaredge2mqtt.core.settings.models import ServiceSettings


def _has_none_values(obj: Any) -> bool:
    """
    Helper function to check if an object contains any None values.

    Recursively checks dictionaries, lists, and nested structures.

    Args:
        obj: The object to check

    Returns:
        True if any None values are found, False otherwise
    """
    if obj is None:
        return True
    if isinstance(obj, dict):
        return any(v is None or _has_none_values(v) for v in obj.values())
    if isinstance(obj, list):
        return any(item is None or _has_none_values(item) for item in obj)
    return False


class TestConfigurationMigrator:
    """Tests for ConfigurationMigrator class."""

    def test_identify_key_and_position(self):
        """Test identifying key and position for numeric suffixes."""
        key, pos = ConfigurationMigrator._identify_key_and_position(["meter0"])
        assert key == "meter0"
        assert pos == 4  # Index of 'r', last non-digit character

        key, pos = ConfigurationMigrator._identify_key_and_position(
            ["follower"]
        )
        assert key == "follower"
        assert pos == 7

    def test_insert_nested_key_simple(self):
        """Test inserting a simple key-value pair."""
        migrator = ConfigurationMigrator(ServiceSettings)
        container = {}

        migrator._insert_nested_key(container, ["interval"], "5")

        assert container == {"interval": "5"}

    def test_insert_nested_key_nested(self):
        """Test inserting nested key-value pairs."""
        migrator = ConfigurationMigrator(ServiceSettings)
        container = {}

        migrator._insert_nested_key(
            container, ["modbus", "host"], "192.168.1.100"
        )
        migrator._insert_nested_key(container, ["modbus", "port"], "1502")

        assert container == {
            "modbus": {"host": "192.168.1.100", "port": "1502"}
        }

    def test_insert_nested_key_with_array(self):
        """Test inserting nested key-value pairs with array indices."""
        migrator = ConfigurationMigrator(ServiceSettings)
        container = {}

        migrator._insert_nested_key(container, ["meter0"], "true")
        migrator._insert_nested_key(container, ["meter1"], "false")
        migrator._insert_nested_key(container, ["meter2"], "true")

        assert container == {"meter": ["true", "false", "true"]}

    def test_extract_secrets(self):
        """Test extracting secrets from configuration."""
        migrator = ConfigurationMigrator(ServiceSettings)
        config_data = {
            "mqtt": {
                "broker": "mqtt.example.com",
                "username": "user",
                "password": "secret123",
            },
            "weather": {"api_key": "api_key_123"},
            "influxdb": {"host": "http://localhost", "token": "token_123"},
            "modbus": {"host": "192.168.1.100"},
        }

        config_data, secrets_data = migrator._extract_secrets(config_data)

        # Check that secrets were extracted in flat format
        assert "mqtt_password" in secrets_data
        assert secrets_data["mqtt_password"] == "secret123"
        assert "weather_api_key" in secrets_data
        assert secrets_data["weather_api_key"] == "api_key_123"
        assert "influxdb_token" in secrets_data
        assert secrets_data["influxdb_token"] == "token_123"

        # Check that secrets were replaced with !secret references
        from solaredge2mqtt.core.settings.migrator import SecretReference

        assert isinstance(config_data["mqtt"]["password"], SecretReference)
        assert config_data["mqtt"]["password"].secret_key == "mqtt_password"
        assert isinstance(config_data["weather"]["api_key"], SecretReference)
        assert (
            config_data["weather"]["api_key"].secret_key == "weather_api_key"
        )
        assert isinstance(config_data["influxdb"]["token"], SecretReference)
        assert config_data["influxdb"]["token"].secret_key == "influxdb_token"

        # Check that non-sensitive data remains
        assert config_data["mqtt"]["broker"] == "mqtt.example.com"
        assert config_data["mqtt"]["username"] == "user"
        assert config_data["influxdb"]["host"] == "http://localhost"
        assert config_data["modbus"]["host"] == "192.168.1.100"

    def test_extract_secrets_no_sensitive_data(self):
        """Test extracting secrets when there is no sensitive data."""
        migrator = ConfigurationMigrator(ServiceSettings)
        config_data = {
            "mqtt": {"broker": "mqtt.example.com", "username": "user"},
            "modbus": {"host": "192.168.1.100"},
        }

        config_data, secrets_data = migrator._extract_secrets(config_data)

        # Check that no secrets were extracted
        assert secrets_data == {}

        # Check that config data is unchanged
        assert config_data["mqtt"]["broker"] == "mqtt.example.com"
        assert config_data["mqtt"]["username"] == "user"
        assert config_data["modbus"]["host"] == "192.168.1.100"

    def test_write_yaml_files(self):
        """Test writing configuration and secrets to YAML files."""
        migrator = ConfigurationMigrator(ServiceSettings)

        config_data = {
            "interval": 5,
            "modbus": {"host": "192.168.1.100", "port": 1502},
        }
        secrets_data = {"mqtt": {"password": "secret123"}}

        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "configuration.yml"
            secrets_file = Path(tmpdir) / "secrets.yml"

            migrator.write_yaml_files(
                config_data, secrets_data, str(config_file), str(secrets_file)
            )

            # Verify files were created
            assert config_file.exists()
            assert secrets_file.exists()

            # Verify content
            with open(config_file, "r", encoding="utf-8") as f:
                loaded_config = yaml.safe_load(f)
                assert loaded_config == config_data

            with open(secrets_file, "r", encoding="utf-8") as f:
                loaded_secrets = yaml.safe_load(f)
                assert loaded_secrets == secrets_data

    def test_write_yaml_files_no_secrets(self):
        """Test writing configuration when there are no secrets."""
        migrator = ConfigurationMigrator(ServiceSettings)

        config_data = {
            "interval": 5,
            "modbus": {"host": "192.168.1.100", "port": 1502},
        }
        secrets_data = {}

        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "configuration.yml"
            secrets_file = Path(tmpdir) / "secrets.yml"

            migrator.write_yaml_files(
                config_data, secrets_data, str(config_file), str(secrets_file)
            )

            # Verify config file was created
            assert config_file.exists()

            # Verify secrets file was NOT created (no secrets to write)
            assert not secrets_file.exists()

    def test_yaml_output_format(self):
        """Test YAML output format (no quotes on booleans/secrets)."""
        migrator = ConfigurationMigrator(ServiceSettings)

        config_data = {
            "interval": 5,
            "modbus": {
                "host": "192.168.1.100",
                "meter": [True, False, True],
                "battery": [True, False],
            },
            "mqtt": {"broker": "mqtt.example.com"},
        }
        secrets_data = {"mqtt_password": "secret123"}

        # Add secret references
        from solaredge2mqtt.core.settings.migrator import SecretReference

        config_data["mqtt"]["password"] = SecretReference("mqtt_password")

        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "configuration.yml"
            secrets_file = Path(tmpdir) / "secrets.yml"

            migrator.write_yaml_files(
                config_data, secrets_data, str(config_file), str(secrets_file)
            )

            # Read the raw YAML text
            with open(config_file, "r", encoding="utf-8") as f:
                yaml_text = f.read()

            # Verify booleans are not quoted
            assert "'true'" not in yaml_text
            assert "'false'" not in yaml_text
            assert '"true"' not in yaml_text
            assert '"false"' not in yaml_text

            # Verify secret references are not quoted
            assert "!secret mqtt_password" in yaml_text
            assert "'mqtt_password'" not in yaml_text
            assert '"mqtt_password"' not in yaml_text

            # Verify the YAML is valid and loads correctly
            with open(config_file, "r", encoding="utf-8") as f:
                # Need to use SecretLoader to handle !secret tags
                from solaredge2mqtt.core.settings.loader import SecretLoader

                SecretLoader.secrets = secrets_data
                loaded = yaml.load(f, Loader=SecretLoader)
                assert loaded["mqtt"]["password"] == "secret123"
                assert loaded["modbus"]["meter"] == [True, False, True]

    def test_extract_from_environment_with_type_conversion(self, monkeypatch):
        """Test extracting from environment with proper type conversion."""
        # Set up environment variables matching user's example
        env_vars = {
            "SE2MQTT_MODBUS__HOST": "192.168.1.100",
            "SE2MQTT_MODBUS__PORT": "5020",
            "SE2MQTT_MODBUS__TIMEOUT": "1",
            "SE2MQTT_MODBUS__METER0": "true",
            "SE2MQTT_MODBUS__METER1": "false",
            "SE2MQTT_MODBUS__METER2": "false",
            "SE2MQTT_MODBUS__BATTERY0": "true",
            "SE2MQTT_MODBUS__BATTERY1": "false",
            "SE2MQTT_ENERGY__RETAIN": "false",
            "SE2MQTT_MQTT__BROKER": "mqtt.example.com",
            "SE2MQTT_MQTT__PASSWORD": "secret123",
            # String type that looks like int
            "SE2MQTT_MONITORING__SITE_ID": "12345",
        }

        # Mock environment variables
        for key, value in env_vars.items():
            monkeypatch.setenv(key, value)

        migrator = ConfigurationMigrator(model_class=ServiceSettings)
        config_data, secrets_data = migrator.extract_from_environment()

        # Verify types are correct based on Pydantic model
        assert config_data["modbus"]["host"] == "192.168.1.100"  # String
        assert config_data["modbus"]["port"] == 5020  # Integer
        assert config_data["modbus"]["timeout"] == 1  # Integer
        assert config_data["modbus"]["meter"] == [
            True,
            False,
            False,
        ]  # Booleans
        assert config_data["modbus"]["battery"] == [True, False]  # Booleans
        assert config_data["energy"]["retain"] is False  # Boolean
        assert config_data["mqtt"]["broker"] == "mqtt.example.com"  # String

        # site_id should be string (not converted to int) because
        # model defines it as str
        # It's extracted to secrets, so check it there
        assert secrets_data["monitoring_site_id"] == "12345"  # String
        assert isinstance(secrets_data["monitoring_site_id"], str)

        # Write to YAML and verify no quotes on booleans
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "configuration.yml"
            secrets_file = Path(tmpdir) / "secrets.yml"

            migrator.write_yaml_files(
                config_data, secrets_data, str(config_file), str(secrets_file)
            )

            with open(config_file, "r", encoding="utf-8") as f:
                yaml_text = f.read()

            # Verify no quoted booleans or integers in output
            assert "'false'" not in yaml_text.lower()
            assert "'true'" not in yaml_text.lower()
            assert '"false"' not in yaml_text.lower()
            assert '"true"' not in yaml_text.lower()
            assert "'1'" not in yaml_text
            assert "'5020'" not in yaml_text

            # Verify the actual boolean/integer values appear correctly
            assert "meter:" in yaml_text or "meter: " in yaml_text
            assert "retain: false" in yaml_text
            assert "retain: false" in yaml_text
            assert "port: 5020" in yaml_text
            assert "timeout: 1" in yaml_text

    def test_remove_null_values(self):
        """Test that null values are removed from nested structures."""
        test_data = {
            "simple_field": "value",
            "null_field": None,
            "nested": {"field1": "value1", "field2": None, "field3": "value3"},
            "list": [1, None, 3, None, 5],
            "nested_list": [{"a": 1, "b": None}, None, {"c": 3}],
            "empty_after_clean": {"all_null": None, "another_null": None},
        }

        cleaned = ConfigurationMigrator._remove_null_values(test_data)

        # Verify structure
        assert "simple_field" in cleaned
        assert "null_field" not in cleaned
        assert "nested" in cleaned
        assert "field2" not in cleaned["nested"]
        assert cleaned["list"] == [1, 3, 5]
        assert len(cleaned["nested_list"]) == 2
        assert "b" not in cleaned["nested_list"][0]
        assert "empty_after_clean" not in cleaned

        # Verify no None values remain using shared helper
        assert not _has_none_values(cleaned)

    def test_extract_from_environment_excludes_none(self, monkeypatch):
        """
        Test that extract_from_environment excludes None values.

        This ensures configuration files don't have 'null' entries for
        optional fields that weren't configured.
        """
        # Set up minimal environment (many optional fields not set)
        env_vars = {
            "SE2MQTT_INTERVAL": "10",
            "SE2MQTT_MODBUS__HOST": "192.168.1.100",
            "SE2MQTT_MODBUS__PORT": "1502",
            "SE2MQTT_MQTT__BROKER": "mqtt.example.com",
            "SE2MQTT_MQTT__PORT": "1883",
        }

        for key, value in env_vars.items():
            monkeypatch.setenv(key, value)

        migrator = ConfigurationMigrator(model_class=ServiceSettings)
        config_data, secrets_data = migrator.extract_from_environment()

        # Verify no None values in extracted data using shared helper
        assert not _has_none_values(config_data)
        assert not _has_none_values(secrets_data)

        # Write to YAML and verify no null in the file
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "configuration.yml"
            secrets_file = Path(tmpdir) / "secrets.yml"

            migrator.write_yaml_files(
                config_data, secrets_data, str(config_file), str(secrets_file)
            )

            with open(config_file, "r", encoding="utf-8") as f:
                yaml_text = f.read()
                assert "null" not in yaml_text.lower()
                assert ": ~" not in yaml_text

    def test_write_yaml_files_permission_error_on_directory(self):
        """Test handling of permission error when creating directory."""
        migrator = ConfigurationMigrator(model_class=ServiceSettings)

        # Use minimal valid config data directly
        config_data = {
            "interval": 5,
            "modbus": {"host": "192.168.1.100", "port": 1502},
        }
        secrets_data = {}

        # Try to write to a directory we can't create
        with tempfile.TemporaryDirectory() as tmpdir:
            readonly_dir = Path(tmpdir) / "readonly"
            readonly_dir.mkdir()
            readonly_dir.chmod(0o444)  # Read-only

            config_file = readonly_dir / "subdir" / "configuration.yml"
            secrets_file = readonly_dir / "subdir" / "secrets.yml"

            import pytest

            with pytest.raises(PermissionError):
                migrator.write_yaml_files(
                    config_data,
                    secrets_data,
                    str(config_file),
                    str(secrets_file),
                )

    def test_write_yaml_files_permission_error_on_file(self):
        """Test handling of permission error when writing file."""
        migrator = ConfigurationMigrator(model_class=ServiceSettings)

        # Use minimal valid config data directly
        config_data = {
            "interval": 5,
            "modbus": {"host": "192.168.1.100", "port": 1502},
        }
        secrets_data = {}

        # Try to write to a read-only file
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "configuration.yml"
            secrets_file = Path(tmpdir) / "secrets.yml"

            # Create a read-only file
            config_file.touch()
            config_file.chmod(0o444)

            import pytest

            with pytest.raises(PermissionError):
                migrator.write_yaml_files(
                    config_data,
                    secrets_data,
                    str(config_file),
                    str(secrets_file),
                )
