try:
    from solaredge2mqtt._version import __version__
except ImportError:
    # No _version.py: this is an unbuilt/uninstalled source checkout (e.g.
    # running straight from a clone without `uv sync`/`pip install .`) -
    # Docker and any other real build install a wheel, which always carries
    # _version.py as a side effect of [tool.setuptools_scm] version_file in
    # pyproject.toml. Fall back to a live git query, which works for a plain
    # checkout as long as .git and setuptools_scm are both present.
    # version_scheme/local_scheme match [tool.setuptools_scm] in
    # pyproject.toml.
    __version__ = "0.0.0-unknown"
    try:
        from setuptools_scm import get_version

        __version__ = get_version(
            root="..",
            relative_to=__file__,
            version_scheme="post-release",
            local_scheme="node-and-date",
        )
    except Exception:
        pass
