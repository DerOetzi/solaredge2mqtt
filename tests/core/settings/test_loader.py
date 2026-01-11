"""Tests for configuration loader module."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import yaml

from solaredge2mqtt.core.settings.loader import ConfigurationLoader
from solaredge2mqtt.core.settings.migrator import EnvironmentReader


class TestEnvironmentReader:
    """Tests for EnvironmentReader class."""

    def test_has_prefix_with_valid_prefix(self):
        """Test prefix checking with valid SE2MQTT_ prefix."""
        assert EnvironmentReader._has_prefix("SE2MQTT_MODBUS__HOST")
        assert EnvironmentReader._has_prefix("se2mqtt_mqtt__broker")
        assert EnvironmentReader._has_prefix("Se2MqTt_InTeRvAl")

    def test_has_prefix_without_prefix(self):
        """Test prefix checking without SE2MQTT_ prefix."""
        assert not EnvironmentReader._has_prefix("MODBUS__HOST")
        assert not EnvironmentReader._has_prefix("MQTT_BROKER")
        assert not EnvironmentReader._has_prefix("PATH")

    @patch.dict(
        "os.environ",
        {
            "SE2MQTT_MODBUS__HOST": "192.168.1.100",
            "SE2MQTT_MQTT__BROKER": "mqtt.example.com",
            "OTHER_VAR": "ignored",
        },
    )
    def test_read_environment(self):
        """Test reading from environment variables."""
        result = list(EnvironmentReader._read_environment())
        keys = [key for key, _ in result]

        assert "SE2MQTT_MODBUS__HOST" in keys
        assert "SE2MQTT_MQTT__BROKER" in keys
        assert "OTHER_VAR" not in keys

    def test_read_dotenv(self):
        """Test reading from .env file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text(
                "SE2MQTT_MODBUS__HOST=192.168.1.100\n"
                "SE2MQTT_MQTT__BROKER=mqtt.example.com\n"
                "# Comment line\n"
                "OTHER_VAR=ignored\n"
            )

            with patch(
                "solaredge2mqtt.core.settings.loader.path.exists",
                return_value=True,
            ):
                with open(env_file, "r", encoding="utf-8") as test_file:
                    with patch(
                        "builtins.open",
                        return_value=test_file,
                    ):
                        result = list(EnvironmentReader._read_dotenv())
                        keys = [key for key, _ in result]

                        assert "SE2MQTT_MODBUS__HOST" in keys
                        assert "SE2MQTT_MQTT__BROKER" in keys
                        assert "OTHER_VAR" not in keys


class TestConfigurationLoader:
    """Tests for ConfigurationLoader class."""

    def test_load_yaml_file(self):
        """Test loading a YAML file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yml", delete=False
        ) as tmpfile:
            yaml_data = {"interval": 5, "modbus": {"host": "192.168.1.100"}}
            yaml.safe_dump(yaml_data, tmpfile)
            tmpfile.flush()

            result = ConfigurationLoader._load_yaml_file(tmpfile.name)

            assert result == yaml_data

            Path(tmpfile.name).unlink()

    def test_load_yaml_file_empty(self):
        """Test loading an empty YAML file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yml", delete=False
        ) as tmpfile:
            tmpfile.write("")
            tmpfile.flush()

            result = ConfigurationLoader._load_yaml_file(tmpfile.name)

            assert result == {}

            Path(tmpfile.name).unlink()

    def test_deep_merge_simple(self):
        """Test deep merging of simple dictionaries."""
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}

        result = ConfigurationLoader._deep_merge(base, override)

        assert result == {"a": 1, "b": 3, "c": 4}

    def test_deep_merge_nested(self):
        """Test deep merging of nested dictionaries."""
        base = {"modbus": {"host": "192.168.1.100", "port": 1502}}
        override = {"modbus": {"port": 1503, "timeout": 1}}

        result = ConfigurationLoader._deep_merge(base, override)

        assert result == {
            "modbus": {"host": "192.168.1.100", "port": 1503, "timeout": 1}
        }

    def test_deep_merge_with_non_dict(self):
        """Test deep merging when override value is not a dict."""
        base = {"modbus": {"host": "192.168.1.100"}}
        override = {"modbus": "new_value"}

        result = ConfigurationLoader._deep_merge(base, override)

        assert result == {"modbus": "new_value"}

    @patch("solaredge2mqtt.core.settings.loader.path.exists")
    def test_load_configuration_no_files(self, mock_exists):
        """Test loading configuration when no YAML files exist."""
        mock_exists.return_value = False

        with patch(
            "solaredge2mqtt.core.settings.loader.ConfigurationLoader._migrate_from_environment"
        ) as mock_migrate:
            mock_migrate.return_value = {"interval": 5}

            result = ConfigurationLoader.load_configuration()

            assert result == {"interval": 5}
            mock_migrate.assert_called_once()

    @patch("solaredge2mqtt.core.settings.loader.path.exists")
    def test_load_configuration_with_config_only(self, mock_exists):
        """Test loading configuration when only config file exists."""
        mock_exists.side_effect = lambda x: x == "config/configuration.yml"

        with patch(
            "solaredge2mqtt.core.settings.loader.ConfigurationLoader._load_yaml_file"
        ) as mock_load:
            mock_load.return_value = {
                "interval": 5,
                "modbus": {"host": "192.168.1.100"},
                "mqtt": {"broker": "mqtt.example.com"},
            }

            result = ConfigurationLoader.load_configuration()

            assert hasattr(result, "interval")
            assert hasattr(result, "modbus")
            assert hasattr(result, "mqtt")
            assert result.modbus.host == "192.168.1.100"
            assert result.mqtt.broker == "mqtt.example.com"

    @patch("solaredge2mqtt.core.settings.loader.path.exists")
    def test_load_configuration_with_both_files(self, mock_exists):
        """Test loading configuration when both config and secrets exist."""
        mock_exists.return_value = True

        # Secrets are loaded first
        secrets_data = {"mqtt_password": "secret"}
        # Config can reference secrets with !secret tag and has required fields
        config_data = {
            "interval": 5,
            "modbus": {"host": "192.168.1.100"},
            "mqtt": {"broker": "mqtt.example.com"},
        }

        with patch(
            "solaredge2mqtt.core.settings.loader.ConfigurationLoader._load_yaml_file"
        ) as mock_load:
            # First call loads secrets, second call loads config
            mock_load.side_effect = [secrets_data, config_data]

            result = ConfigurationLoader.load_configuration()

            assert result.interval == 5
            assert result.modbus.host == "192.168.1.100"
            assert result.mqtt.broker == "mqtt.example.com"
            # Secrets are available in SecretLoader.secrets but not merged into result
            # unless referenced via !secret tag in the config

    @patch("solaredge2mqtt.core.settings.loader.path.exists")
    @patch("solaredge2mqtt.core.settings.loader.ConfigurationLoader._is_file_empty")
    def test_load_configuration_empty_file_triggers_migration(self, mock_is_empty, mock_exists):
        """Test loading empty configuration file triggers migration."""
        mock_exists.return_value = True
        mock_is_empty.return_value = True

        with patch(
            "solaredge2mqtt.core.settings.loader.ConfigurationLoader._migrate_from_environment"
        ) as mock_migrate:
            from solaredge2mqtt.core.settings.models import ServiceSettings
            mock_migrate.return_value = ServiceSettings(
                modbus={"host": "192.168.1.100"},
                mqtt={"broker": "mqtt.example.com"},
            )

            result = ConfigurationLoader.load_configuration()

            mock_migrate.assert_called_once()
            assert result.modbus.host == "192.168.1.100"
            assert result.mqtt.broker == "mqtt.example.com"

    def test_is_file_empty_with_empty_file(self):
        """Test checking if file is empty with empty file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yml", delete=False
        ) as tmpfile:
            tmpfile.write("")
            tmpfile.flush()

            result = ConfigurationLoader._is_file_empty(tmpfile.name)

            assert result is True

            Path(tmpfile.name).unlink()

    def test_is_file_empty_with_whitespace_only(self):
        """Test checking if file is empty with whitespace only."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yml", delete=False
        ) as tmpfile:
            tmpfile.write("   \n\n  \t  \n")
            tmpfile.flush()

            result = ConfigurationLoader._is_file_empty(tmpfile.name)

            assert result is True

            Path(tmpfile.name).unlink()

    def test_is_file_empty_with_content(self):
        """Test checking if file is empty with actual content."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yml", delete=False
        ) as tmpfile:
            tmpfile.write("interval: 5\n")
            tmpfile.flush()

            result = ConfigurationLoader._is_file_empty(tmpfile.name)

            assert result is False

            Path(tmpfile.name).unlink()

    def test_is_file_empty_nonexistent_file(self):
        """Test checking if file is empty with nonexistent file."""
        result = ConfigurationLoader._is_file_empty("/nonexistent/file.yml")

        assert result is False

    def test_copy_example_files_success(self):
        """Test copying example files to target locations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "configuration.yml"
            secrets_file = Path(tmpdir) / "secrets.yml"
            
            # Copy example files
            ConfigurationLoader._copy_example_files(
                str(config_file), str(secrets_file)
            )
            
            # Check files were created
            assert config_file.exists()
            assert secrets_file.exists()
            
            # Check secrets file has correct permissions (600)
            import stat
            secrets_stat = secrets_file.stat()
            # On Unix: should be -rw-------
            # Just check it's not world/group readable
            assert not (secrets_stat.st_mode & stat.S_IRGRP)
            assert not (secrets_stat.st_mode & stat.S_IROTH)

    @patch("solaredge2mqtt.core.settings.loader.EnvironmentReader.read_all")
    @patch("solaredge2mqtt.core.settings.loader.path.exists")
    def test_migrate_from_environment_no_env_vars(
        self, mock_exists, mock_read_all
    ):
        """Test migration when no environment variables exist (new install)."""
        mock_exists.return_value = False
        mock_read_all.return_value = {}  # No environment variables
        
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "configuration.yml"
            secrets_file = Path(tmpdir) / "secrets.yml"
            
            # Should exit with code 0 after copying examples
            try:
                ConfigurationLoader._migrate_from_environment(
                    str(config_file), str(secrets_file)
                )
                raise AssertionError("Expected sys.exit(0)")
            except SystemExit as e:
                assert e.code == 0
                
            # Check example files were copied
            assert config_file.exists()
            assert secrets_file.exists()



class TestSecretLoader:
    """Tests for SecretLoader and !secret tag functionality."""

    def test_secret_tag_simple(self):
        """Test loading configuration with !secret tag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create secrets file
            secrets_file = Path(tmpdir) / "secrets.yml"
            secrets_file.write_text("mqtt_password: secret123\n")

            # Create config file with !secret tag and required fields
            config_file = Path(tmpdir) / "configuration.yml"
            config_file.write_text(
                "modbus:\n"
                "  host: 192.168.1.100\n"
                "mqtt:\n"
                "  broker: mqtt.example.com\n"
                "  password: !secret mqtt_password\n"
            )

            # Load configuration
            result = ConfigurationLoader.load_configuration(tmpdir)

            assert result.modbus.host == "192.168.1.100"
            assert result.mqtt.broker == "mqtt.example.com"
            assert result.mqtt.password.get_secret_value() == "secret123"

    def test_secret_tag_nested(self):
        """Test loading configuration with nested !secret tag."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create secrets file with nested structure
            secrets_file = Path(tmpdir) / "secrets.yml"
            secrets_file.write_text("mqtt:\n  password: nested_secret\n")

            # Create config file with !secret tag using dot notation and required fields
            config_file = Path(tmpdir) / "configuration.yml"
            config_file.write_text(
                "modbus:\n"
                "  host: 192.168.1.100\n"
                "mqtt:\n"
                "  broker: mqtt.example.com\n"
                "  password: !secret mqtt.password\n"
            )

            # Load configuration
            result = ConfigurationLoader.load_configuration(tmpdir)

            assert result.modbus.host == "192.168.1.100"
            assert result.mqtt.broker == "mqtt.example.com"
            assert result.mqtt.password.get_secret_value() == "nested_secret"

    def test_secret_tag_missing_secret(self):
        """Test loading configuration with missing secret raises error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create empty secrets file
            secrets_file = Path(tmpdir) / "secrets.yml"
            secrets_file.write_text("other_key: value\n")

            # Create config file with !secret tag
            config_file = Path(tmpdir) / "configuration.yml"
            config_file.write_text(
                "mqtt:\n" "  password: !secret mqtt_password\n"
            )

            # Load configuration should raise error
            try:
                ConfigurationLoader.load_configuration(tmpdir)
                raise AssertionError("Expected ValueError for missing secret")
            except ValueError as e:
                assert "mqtt_password" in str(e)
                assert "not found" in str(e)
