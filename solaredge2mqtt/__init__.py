try:
    from solaredge2mqtt._version import __version__
except ImportError:
    # No _version.py: neither built (uv build/uv sync/pip install) nor frozen
    # for Docker (freeze_version.py) - fall back to a live git query, which
    # works for a plain checkout as long as .git and setuptools_scm are both
    # present. version_scheme/local_scheme match [tool.setuptools_scm] in
    # pyproject.toml, same reasoning as freeze_version.py.
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
