"""Tests for the solaredge2mqtt root module."""

from solaredge2mqtt import __version__


class TestVersion:
    """Tests for version information."""

    def test_version_is_string(self):
        """Test that __version__ is a string."""
        assert isinstance(__version__, str)

    def test_version_not_empty(self):
        """Test that __version__ is not empty."""
        assert len(__version__) > 0
