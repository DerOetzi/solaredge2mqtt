"""Tests for package initialization version resolution paths."""

import builtins
import importlib
import io
import json
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import patch


def _reload_package() -> ModuleType:
    """Reload package module to re-run module-level init code."""
    sys.modules.pop("solaredge2mqtt", None)
    return importlib.import_module("solaredge2mqtt")


def test_version_from_version_file(monkeypatch):
    """Use version from version.json when file exists and is valid."""

    def fake_exists(self: Path) -> bool:
        return self.name == "version.json"

    def fake_open(self: Path, encoding: str = "utf-8"):
        del encoding
        return io.StringIO(json.dumps({"version": "1.2.3-test"}))

    monkeypatch.setattr(Path, "exists", fake_exists)
    monkeypatch.setattr(Path, "open", fake_open)

    module = _reload_package()

    assert module.__version__ == "1.2.3-test"


def test_version_file_read_error_falls_back_to_default(monkeypatch):
    """Keep default version when version file exists but fails to read."""

    def fake_exists(self: Path) -> bool:
        return self.name == "version.json"

    def fake_open(self: Path, encoding: str = "utf-8"):
        del self, encoding
        raise OSError("cannot read")

    monkeypatch.setattr(Path, "exists", fake_exists)
    monkeypatch.setattr(Path, "open", fake_open)

    module = _reload_package()

    assert module.__version__ == "0.0.0-unknown"


def test_version_from_pkg_metadata_when_no_version_file(monkeypatch):
    """Use package metadata fallback when no version file exists."""

    def fake_exists(self: Path) -> bool:
        return False

    monkeypatch.setattr(Path, "exists", fake_exists)

    module = _reload_package()

    assert isinstance(module.__version__, str)
    assert len(module.__version__) > 0


def test_version_from_setuptools_scm_when_available(monkeypatch):
    """Use setuptools_scm get_version when version file is absent."""

    def fake_exists(self: Path) -> bool:
        return False

    monkeypatch.setattr(Path, "exists", fake_exists)

    fake_scm = ModuleType("setuptools_scm")
    setattr(fake_scm, "get_version", lambda **kwargs: "2.3.4-scm")  # noqa: ARG005

    with patch.dict(sys.modules, {"setuptools_scm": fake_scm}):
        module = _reload_package()

    assert module.__version__ == "2.3.4-scm"


def test_version_setuptools_scm_failure_keeps_default(monkeypatch):
    """If setuptools_scm fails, keep default version string."""

    def fake_exists(self: Path) -> bool:
        return False

    monkeypatch.setattr(Path, "exists", fake_exists)

    fake_scm = ModuleType("setuptools_scm")

    def _raise(**kwargs):  # noqa: ARG001
        raise RuntimeError("scm failed")

    setattr(fake_scm, "get_version", _raise)

    with patch.dict(sys.modules, {"setuptools_scm": fake_scm}):
        module = _reload_package()

    assert isinstance(module.__version__, str)


def test_version_from_pkg_metadata_when_setuptools_scm_unavailable(monkeypatch):
    """Use package metadata when setuptools_scm import is unavailable."""

    def fake_exists(self: Path) -> bool:
        return False

    monkeypatch.setattr(Path, "exists", fake_exists)

    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "setuptools_scm":
            raise ImportError("missing setuptools_scm")
        return original_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=fake_import):
        module = _reload_package()

    assert isinstance(module.__version__, str)
    assert len(module.__version__) > 0


def test_version_pkg_metadata_failure_keeps_default_when_scm_unavailable(monkeypatch):
    """Keep default when both setuptools_scm import and pkg metadata fail."""

    def fake_exists(self: Path) -> bool:
        return False

    monkeypatch.setattr(Path, "exists", fake_exists)

    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "setuptools_scm":
            raise ImportError("missing setuptools_scm")
        return original_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=fake_import):
        with patch("importlib.metadata.version", side_effect=RuntimeError("no pkg")):
            module = _reload_package()

    assert module.__version__ == "0.0.0-unknown"
