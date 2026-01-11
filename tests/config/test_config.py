"""Tests for the config module."""
from os import path

from solaredge2mqtt.config import get_example_files


class TestGetExampleFiles:
    """Test the get_example_files function."""

    def test_get_example_files_returns_tuple(self):
        """Test that get_example_files returns a tuple of two paths."""
        result = get_example_files()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_get_example_files_returns_absolute_paths(self):
        """Test that returned paths are absolute."""
        config_path, secrets_path = get_example_files()
        assert path.isabs(config_path)
        assert path.isabs(secrets_path)

    def test_get_example_files_paths_exist(self):
        """Test that the example files actually exist."""
        config_path, secrets_path = get_example_files()
        assert path.exists(config_path), (
            f"Configuration example file not found: {config_path}"
        )
        assert path.exists(secrets_path), (
            f"Secrets example file not found: {secrets_path}"
        )

    def test_get_example_files_correct_filenames(self):
        """Test that returned paths have correct filenames."""
        config_path, secrets_path = get_example_files()
        assert config_path.endswith("configuration.yml.example")
        assert secrets_path.endswith("secrets.yml.example")

    def test_get_example_files_in_same_directory(self):
        """Test that both example files are in the same directory."""
        config_path, secrets_path = get_example_files()
        config_dir = path.dirname(config_path)
        secrets_dir = path.dirname(secrets_path)
        assert config_dir == secrets_dir

    def test_get_example_files_are_regular_files(self):
        """Test that the example files are regular files."""
        config_path, secrets_path = get_example_files()
        assert path.isfile(config_path)
        assert path.isfile(secrets_path)

    def test_get_example_files_are_readable(self):
        """Test that the example files can be opened and read."""
        config_path, secrets_path = get_example_files()
        
        # Test configuration example is readable
        with open(config_path, "r", encoding="utf-8") as f:
            config_content = f.read()
            assert len(config_content) > 0
            
        # Test secrets example is readable
        with open(secrets_path, "r", encoding="utf-8") as f:
            secrets_content = f.read()
            assert len(secrets_content) > 0
