"""Tests for migrate_config.py top-level script."""

import os
import runpy
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

WORKSPACE_ROOT = Path(__file__).parent.parent


def _make_env() -> dict[str, str]:
    base = {k: v for k, v in os.environ.items() if not k.upper().startswith("SE2MQTT_")}
    base.update(
        {
            "SE2MQTT_MODBUS__HOST": "192.168.1.1",  # noqa: S1313
            "SE2MQTT_MODBUS__PASSWORD": "secret123",  # noqa: S2068
            "SE2MQTT_MQTT__BROKER": "mqtt.local",
        }
    )
    return base


def _make_env_with_tls(use_tls: str) -> dict[str, str]:
    env = _make_env()
    env["SE2MQTT_MQTT__USE_TLS"] = use_tls
    return env


class TestMigrateConfigMain:
    """Tests for migrate_config.py's main() function behaviour."""

    def test_dry_run_prints_config_no_files_written(self, tmp_path: Path):
        """--dry-run outputs YAML to stdout and writes no files."""
        result = subprocess.run(
            [
                sys.executable,
                str(WORKSPACE_ROOT / "migrate_config.py"),
                "--output-dir",
                str(tmp_path),
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            env=_make_env(),
        )

        assert result.returncode == 0, result.stderr
        assert "DRY RUN" in result.stdout
        assert not (tmp_path / "configuration.yml").exists()
        assert not (tmp_path / "secrets.yml").exists()

    def test_normal_run_writes_config_and_secrets(self, tmp_path: Path):
        """Normal run writes configuration.yml and secrets.yml."""
        result = subprocess.run(
            [
                sys.executable,
                str(WORKSPACE_ROOT / "migrate_config.py"),
                "--output-dir",
                str(tmp_path),
            ],
            capture_output=True,
            text=True,
            env=_make_env(),
        )

        assert result.returncode == 0, result.stderr
        config_file = tmp_path / "configuration.yml"
        assert config_file.exists()
        data = yaml.safe_load(config_file.read_text(encoding="utf-8"))
        assert isinstance(data, dict)

    def test_backup_flag_renames_existing_files(self, tmp_path: Path):
        """--backup renames existing config/secrets files before writing new ones."""
        config_file = tmp_path / "configuration.yml"
        secrets_file = tmp_path / "secrets.yml"
        config_file.write_text("old: config\n", encoding="utf-8")
        secrets_file.write_text("old: secrets\n", encoding="utf-8")

        result = subprocess.run(
            [
                sys.executable,
                str(WORKSPACE_ROOT / "migrate_config.py"),
                "--output-dir",
                str(tmp_path),
                "--backup",
            ],
            capture_output=True,
            text=True,
            env=_make_env(),
        )

        assert result.returncode == 0, result.stderr
        backups = list(tmp_path.glob("configuration.yml.backup.*"))
        assert len(backups) == 1
        assert backups[0].read_text(encoding="utf-8") == "old: config\n"

    def test_output_dir_is_created_when_missing(self, tmp_path: Path):
        """Missing --output-dir is created automatically."""
        out_dir = tmp_path / "nested" / "dir"
        assert not out_dir.exists()

        result = subprocess.run(
            [
                sys.executable,
                str(WORKSPACE_ROOT / "migrate_config.py"),
                "--output-dir",
                str(out_dir),
            ],
            capture_output=True,
            text=True,
            env=_make_env(),
        )

        assert result.returncode == 0, result.stderr
        assert out_dir.exists()

    def test_migration_complete_message_printed(self, tmp_path: Path):
        """Normal run prints the 'Migration complete!' confirmation message."""
        result = subprocess.run(
            [
                sys.executable,
                str(WORKSPACE_ROOT / "migrate_config.py"),
                "--output-dir",
                str(tmp_path),
            ],
            capture_output=True,
            text=True,
            env=_make_env(),
        )

        assert result.returncode == 0, result.stderr
        assert "Migration complete!" in result.stdout

    def test_dry_run_shows_both_section_headers(self, tmp_path: Path):
        """Dry run prints headers for both configuration and secrets output."""
        result = subprocess.run(
            [
                sys.executable,
                str(WORKSPACE_ROOT / "migrate_config.py"),
                "--output-dir",
                str(tmp_path),
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            env=_make_env(),
        )

        assert result.returncode == 0, result.stderr
        assert "Configuration" in result.stdout
        assert "Secrets" in result.stdout

    def test_input_flag_accepted(self, tmp_path: Path):
        """--input flag is accepted without error (uses custom .env path)."""
        dotenv = tmp_path / "custom.env"
        dotenv.write_text("", encoding="utf-8")

        result = subprocess.run(
            [
                sys.executable,
                str(WORKSPACE_ROOT / "migrate_config.py"),
                "--input",
                str(dotenv),
                "--output-dir",
                str(tmp_path),
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            env=_make_env(),
        )

        assert result.returncode == 0, result.stderr

    def test_short_flags_work(self, tmp_path: Path):
        """Short flags -o and -d are accepted equivalents."""
        result = subprocess.run(
            [
                sys.executable,
                str(WORKSPACE_ROOT / "migrate_config.py"),
                "-o",
                str(tmp_path),
                "-d",
            ],
            capture_output=True,
            text=True,
            env=_make_env(),
        )

        assert result.returncode == 0, result.stderr
        assert "DRY RUN" in result.stdout

    def test_secrets_file_not_written_when_no_secrets(self, tmp_path: Path):
        """Secrets file is not written if no secret fields are present."""
        env = {
            k: v for k, v in os.environ.items() if not k.upper().startswith("SE2MQTT_")
        }
        env.update(
            {
                "SE2MQTT_MODBUS__HOST": "10.0.0.1",  # noqa: S1313
                "SE2MQTT_MQTT__BROKER": "mqtt.local",
            }
        )
        result = subprocess.run(
            [
                sys.executable,
                str(WORKSPACE_ROOT / "migrate_config.py"),
                "--output-dir",
                str(tmp_path),
            ],
            capture_output=True,
            text=True,
            env=env,
        )

        assert result.returncode == 0, result.stderr
        # secrets.yml should NOT exist (no secrets to write)
        assert not (tmp_path / "secrets.yml").exists()

    def test_use_tls_true_is_migrated_to_boolean(self, tmp_path: Path):
        """SE2MQTT_MQTT__USE_TLS=true is written as boolean true."""
        result = subprocess.run(
            [
                sys.executable,
                str(WORKSPACE_ROOT / "migrate_config.py"),
                "--output-dir",
                str(tmp_path),
            ],
            capture_output=True,
            text=True,
            env=_make_env_with_tls("true"),
        )

        assert result.returncode == 0, result.stderr
        config_data = yaml.safe_load(
            (tmp_path / "configuration.yml").read_text(encoding="utf-8")
        )
        assert config_data["mqtt"]["use_tls"] is True

    def test_use_tls_false_is_migrated_to_boolean(self, tmp_path: Path):
        """SE2MQTT_MQTT__USE_TLS=false is written as boolean false."""
        result = subprocess.run(
            [
                sys.executable,
                str(WORKSPACE_ROOT / "migrate_config.py"),
                "--output-dir",
                str(tmp_path),
            ],
            capture_output=True,
            text=True,
            env=_make_env_with_tls("false"),
        )

        assert result.returncode == 0, result.stderr
        config_data = yaml.safe_load(
            (tmp_path / "configuration.yml").read_text(encoding="utf-8")
        )
        assert config_data["mqtt"]["use_tls"] is False


class TestMigrateConfigUnit:
    """Unit-level tests for migrate_config.main() using mocks."""

    def test_main_calls_write_yaml_files_on_normal_run(self, tmp_path: Path):
        """main() calls migrator.write_yaml_files when not in dry_run mode."""
        mock_migrator = MagicMock()
        mock_migrator.extract_from_environment.return_value = (
            {"modbus": {}},
            {"modbus_password": "s"},  # noqa: S2068
        )

        with (
            patch("migrate_config.ConfigurationMigrator", return_value=mock_migrator),
            patch("sys.argv", ["migrate_config.py", "--output-dir", str(tmp_path)]),
        ):
            from migrate_config import main

            main()

        mock_migrator.write_yaml_files.assert_called_once()

    def test_main_does_not_call_write_yaml_files_on_dry_run(self, tmp_path: Path):
        """main() does NOT call write_yaml_files in dry_run mode."""
        mock_migrator = MagicMock()
        mock_migrator.extract_from_environment.return_value = (
            {"modbus": {}},
            {},
        )

        with (
            patch("migrate_config.ConfigurationMigrator", return_value=mock_migrator),
            patch(
                "sys.argv",
                ["migrate_config.py", "--output-dir", str(tmp_path), "--dry-run"],
            ),
        ):
            from migrate_config import main

            main()

        mock_migrator.write_yaml_files.assert_not_called()

    def test_main_creates_missing_output_directory(self, tmp_path: Path):
        """main() creates --output-dir when it does not exist."""
        output_dir = tmp_path / "new" / "nested"
        assert not output_dir.exists()

        mock_migrator = MagicMock()
        mock_migrator.extract_from_environment.return_value = (
            {"modbus": {}},
            {},
        )

        with (
            patch("migrate_config.ConfigurationMigrator", return_value=mock_migrator),
            patch(
                "sys.argv",
                [
                    "migrate_config.py",
                    "--output-dir",
                    str(output_dir),
                    "--dry-run",
                ],
            ),
        ):
            from migrate_config import main

            main()

        assert output_dir.exists()

    def test_main_backup_renames_existing_files(self, tmp_path: Path):
        """main() backup mode renames existing config and secrets files."""
        config_file = tmp_path / "configuration.yml"
        secrets_file = tmp_path / "secrets.yml"
        config_file.write_text("old: config\n", encoding="utf-8")
        secrets_file.write_text("old: secrets\n", encoding="utf-8")

        mock_migrator = MagicMock()
        mock_migrator.extract_from_environment.return_value = (
            {"modbus": {}},
            {},
        )

        with (
            patch("migrate_config.ConfigurationMigrator", return_value=mock_migrator),
            patch(
                "sys.argv",
                [
                    "migrate_config.py",
                    "--output-dir",
                    str(tmp_path),
                    "--backup",
                    "--dry-run",
                ],
            ),
            patch("builtins.print") as mock_print,
        ):
            from migrate_config import main

            main()

        backup_config = list(tmp_path.glob("configuration.yml.backup.*"))
        backup_secrets = list(tmp_path.glob("secrets.yml.backup.*"))
        assert len(backup_config) == 1
        assert len(backup_secrets) == 1
        printed = "\n".join(str(call.args[0]) for call in mock_print.call_args_list)
        assert "Created backup:" in printed

    def test_main_backup_skips_missing_files(self, tmp_path: Path):
        """main() backup mode should skip rename when files are absent."""
        mock_migrator = MagicMock()
        mock_migrator.extract_from_environment.return_value = (
            {"modbus": {}},
            {},
        )

        with (
            patch("migrate_config.ConfigurationMigrator", return_value=mock_migrator),
            patch(
                "sys.argv",
                [
                    "migrate_config.py",
                    "--output-dir",
                    str(tmp_path),
                    "--backup",
                    "--dry-run",
                ],
            ),
            patch("builtins.print") as mock_print,
        ):
            from migrate_config import main

            main()

        assert list(tmp_path.glob("configuration.yml.backup.*")) == []
        assert list(tmp_path.glob("secrets.yml.backup.*")) == []
        printed = "\n".join(str(call.args[0]) for call in mock_print.call_args_list)
        assert "Created backup:" not in printed

    def test_main_guard_executes_main(self, tmp_path: Path):
        """Executing script as __main__ should invoke main() guard path."""
        with (
            patch(
                "sys.argv",
                [
                    "migrate_config.py",
                    "--output-dir",
                    str(tmp_path),
                    "--dry-run",
                ],
            ),
            patch.dict(os.environ, _make_env(), clear=False),
        ):
            runpy.run_path(
                str(WORKSPACE_ROOT / "migrate_config.py"), run_name="__main__"
            )
