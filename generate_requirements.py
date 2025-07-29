#!/usr/bin/env python3
from pathlib import Path

import tomli

pyproject = Path("pyproject.toml")
with pyproject.open("rb") as f:
    data = tomli.load(f)

project = data.get("project", {})
dependencies = project.get("dependencies", [])
optional = project.get("optional-dependencies", {})

# requirements.txt: alle deps + forecast
requirements_all = sorted(set(dependencies + optional.get("forecast", [])))

# requirements-armv7.txt: nur deps
requirements_arm = sorted(set(dependencies))

Path("requirements.txt").write_text("\n".join(requirements_all) + "\n")
Path("requirements-armv7.txt").write_text("\n".join(requirements_arm) + "\n")

print("✅ requirements.txt und requirements-armv7.txt wurden generiert.")
