"""Tests for __main__ module."""

import runpy
import sys
from unittest.mock import patch


class TestMain:
    """Tests for main function."""

    def test_main_with_default_config_dir(self):
        """Test main function with default config directory."""
        from solaredge2mqtt.__main__ import main

        with patch("solaredge2mqtt.__main__.run") as mock_run:
            with patch.object(sys, "argv", ["solaredge2mqtt"]):
                main()

            mock_run.assert_called_once_with(config_dir="config")

    def test_main_with_custom_config_dir(self):
        """Test main function with custom config directory."""
        from solaredge2mqtt.__main__ import main

        with patch("solaredge2mqtt.__main__.run") as mock_run:
            with patch.object(
                sys, "argv", ["solaredge2mqtt", "--config-dir", "/custom/config"]
            ):
                main()

            mock_run.assert_called_once_with(config_dir="/custom/config")

    def test_main_calls_run(self):
        """Test that main calls run function."""
        from solaredge2mqtt.__main__ import main

        with patch("solaredge2mqtt.__main__.run") as mock_run:
            with patch.object(sys, "argv", ["solaredge2mqtt"]):
                main()

            assert mock_run.called

    def test_main_argparse_config_dir_help(self):
        """Test argparse configuration for config-dir argument."""
        import argparse

        # Create parser to test
        parser = argparse.ArgumentParser(
            description="SolarEdge2MQTT - Bridge SolarEdge data to MQTT"
        )
        parser.add_argument(
            "--config-dir",
            type=str,
            default="config",
            help="Path to configuration directory (default: config)",
        )

        # Test parsing with default
        args = parser.parse_args([])
        assert args.config_dir == "config"

        # Test parsing with custom value
        args = parser.parse_args(["--config-dir", "/custom"])
        assert args.config_dir == "/custom"

    def test_main_guard_executes_module(self):
        """Test __name__ == '__main__' guard executes main in-process."""
        with patch("solaredge2mqtt.service.run") as mock_run:
            with patch.object(sys, "argv", ["solaredge2mqtt"]):
                runpy.run_module("solaredge2mqtt.__main__", run_name="__main__")

        mock_run.assert_called_once_with(config_dir="config")
