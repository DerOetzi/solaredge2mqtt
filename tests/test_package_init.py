"""Tests for package initialization version resolution paths."""

import builtins
import importlib
import sys
from types import ModuleType
from unittest.mock import patch


def _reload_package() -> ModuleType:
    """Reload package module to re-run module-level init code.

    Does not touch sys.modules["solaredge2mqtt._version"] itself - callers
    control that submodule's presence/absence via patch.dict/_block_import,
    and popping it here would undo whatever they just set up.

    The original module object is put back afterwards. Importing the package
    again builds a fresh module object that carries none of the submodule
    attributes the already imported submodules had set on the old one, so
    leaving it in sys.modules breaks every later `solaredge2mqtt.core...`
    attribute lookup in the same process - which is what monkeypatch does to
    resolve a dotted target. The returned object stays valid for assertions.
    """
    original = sys.modules.pop("solaredge2mqtt", None)

    try:
        return importlib.import_module("solaredge2mqtt")
    finally:
        if original is not None:
            sys.modules["solaredge2mqtt"] = original


def _block_import(*names_to_block: str):
    """Patch builtins.__import__ to raise ImportError for the given names."""
    original_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name in names_to_block:
            raise ImportError(f"missing {name}")
        return original_import(name, *args, **kwargs)

    return patch("builtins.__import__", side_effect=fake_import)


def test_version_from_version_file():
    """Use __version__ from solaredge2mqtt._version when it is importable."""
    fake_version_module = ModuleType("solaredge2mqtt._version")
    setattr(fake_version_module, "__version__", "1.2.3-test")

    with patch.dict(sys.modules, {"solaredge2mqtt._version": fake_version_module}):
        module = _reload_package()

    assert module.__version__ == "1.2.3-test"


def test_version_from_setuptools_scm_when_version_file_absent():
    """Fall back to a live setuptools_scm query when _version.py is missing."""
    fake_scm = ModuleType("setuptools_scm")
    setattr(fake_scm, "get_version", lambda **kwargs: "2.3.4-scm")  # noqa: ARG005

    with _block_import("solaredge2mqtt._version"):
        with patch.dict(sys.modules, {"setuptools_scm": fake_scm}):
            module = _reload_package()

    assert module.__version__ == "2.3.4-scm"


def test_setuptools_scm_called_with_matching_scheme():
    """The fallback query must use the same scheme as [tool.setuptools_scm]."""
    captured_kwargs = {}

    def fake_get_version(**kwargs):
        captured_kwargs.update(kwargs)
        return "2.3.4-scm"

    fake_scm = ModuleType("setuptools_scm")
    setattr(fake_scm, "get_version", fake_get_version)

    with _block_import("solaredge2mqtt._version"):
        with patch.dict(sys.modules, {"setuptools_scm": fake_scm}):
            _reload_package()

    assert captured_kwargs["version_scheme"] == "post-release"
    assert captured_kwargs["local_scheme"] == "node-and-date"


def test_version_setuptools_scm_failure_keeps_default():
    """If the live query fails, keep the hardcoded default version string."""

    def _raise(**kwargs):  # noqa: ARG001
        raise RuntimeError("scm failed")

    fake_scm = ModuleType("setuptools_scm")
    setattr(fake_scm, "get_version", _raise)

    with _block_import("solaredge2mqtt._version"):
        with patch.dict(sys.modules, {"setuptools_scm": fake_scm}):
            module = _reload_package()

    assert module.__version__ == "0.0.0-unknown"


def test_version_setuptools_scm_import_error_keeps_default():
    """If setuptools_scm itself can't be imported, keep the default version."""
    with _block_import("solaredge2mqtt._version", "setuptools_scm"):
        module = _reload_package()

    assert module.__version__ == "0.0.0-unknown"
