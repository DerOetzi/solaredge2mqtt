#!/usr/bin/env python3
from setuptools_scm import get_version

VERSION_FILE = "solaredge2mqtt/_version.py"


def generate_version_file() -> None:
    # version_scheme/local_scheme must match [tool.setuptools_scm] in
    # pyproject.toml: get_version() does not read that config on its own,
    # it only applies when setuptools_scm runs as part of an actual build
    # (uv build, uv sync, pip install .) - which the Docker build
    # deliberately never does, hence calling it directly here instead.
    version = get_version(
        root=".",
        relative_to=__file__,
        version_scheme="post-release",
        local_scheme="node-and-date",
        version_file=VERSION_FILE,
    )
    print(f"Generated {VERSION_FILE} with version {version}")


if __name__ == "__main__":
    generate_version_file()
