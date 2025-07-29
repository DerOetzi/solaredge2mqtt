import json
from pathlib import Path

from setuptools_scm import get_version


def generate_version_json():
    version = get_version(root=".", relative_to=__file__)
    data = {"version": version}
    path = Path("solaredge2mqtt/version.json")
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")  # sauberes Newline am Ende der Datei
    print(f"Generated {path} with version {version}")


if __name__ == "__main__":
    generate_version_json()
