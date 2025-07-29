import json
from importlib.metadata import version as pkg_version
from pathlib import Path

try:
    from setuptools_scm import get_version
except ImportError:
    get_version = None

__version__ = "0.0.0-unknown"

version_file = Path(__file__).parent / "version.json"
if version_file.exists():
    try:
        with version_file.open(encoding="utf-8") as f:
            __version__ = json.load(f)["version"]
    except Exception:
        pass
elif get_version is not None:
    try:
        __version__ = get_version(root="..", relative_to=__file__)
    except Exception:
        pass
else:
    try:
        __version__ = pkg_version("solaredge2mqtt")
    except Exception:
        pass
