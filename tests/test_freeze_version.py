"""Tests for freeze_version.py script."""

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import ANY, patch

import pytest


class TestGenerateVersionFile:
    """Unit tests for generate_version_file, with get_version mocked out."""

    def test_calls_get_version_with_matching_scheme(self):
        """generate_version_file must pass the same scheme as pyproject.toml."""
        with patch("freeze_version.get_version", return_value="1.2.3") as mock_get:
            from freeze_version import generate_version_file

            generate_version_file()

        mock_get.assert_called_once_with(
            root=".",
            relative_to=ANY,
            version_scheme="post-release",
            local_scheme="node-and-date",
            version_file="solaredge2mqtt/_version.py",
        )

    def test_prints_generated_path_and_version(self, capsys: pytest.CaptureFixture):
        """generate_version_file prints the output path and resolved version."""
        with patch("freeze_version.get_version", return_value="2.0.0"):
            from freeze_version import generate_version_file

            generate_version_file()

        captured = capsys.readouterr()
        assert "solaredge2mqtt/_version.py" in captured.out
        assert "2.0.0" in captured.out


class TestGenerateVersionFileIntegration:
    """Integration tests exercising the real setuptools_scm write path.

    Writing the file is now setuptools_scm's own job (version_file=...), not
    freeze_version.py's - mocking get_version out (as the unit tests above do)
    bypasses that entirely, so these run the real script against
    SETUPTOOLS_SCM_PRETEND_VERSION to verify the file actually lands with the
    expected content.
    """

    def _copy_script_into(self, tmp_path: Path) -> None:
        script_copy = tmp_path / "freeze_version.py"
        script_copy.write_text(
            (Path(__file__).parent.parent / "freeze_version.py").read_text(
                encoding="utf-8"
            ),
            encoding="utf-8",
        )
        (tmp_path / "solaredge2mqtt").mkdir()

    def test_writes_version_file_with_pretend_version(self, tmp_path: Path):
        self._copy_script_into(tmp_path)

        result = subprocess.run(
            [sys.executable, "freeze_version.py"],
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
            env={**os.environ, "SETUPTOOLS_SCM_PRETEND_VERSION": "1.2.3"},
        )
        assert result.returncode == 0, result.stderr

        content = (tmp_path / "solaredge2mqtt" / "_version.py").read_text(
            encoding="utf-8"
        )
        assert "__version__ = version = '1.2.3'" in content

    def test_prints_generated_path(self, tmp_path: Path):
        self._copy_script_into(tmp_path)

        result = subprocess.run(
            [sys.executable, "freeze_version.py"],
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
            env={**os.environ, "SETUPTOOLS_SCM_PRETEND_VERSION": "4.5.6"},
        )

        assert result.returncode == 0
        assert "solaredge2mqtt/_version.py" in result.stdout
        assert "4.5.6" in result.stdout

    def test_main_block_guard_executes_generate_version_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """The if __name__ == '__main__' guard is exercised via runpy.

        The script must run from its copy inside tmp_path, not the real repo
        path: version_file's write target resolves relative to __file__ (via
        relative_to=__file__ in generate_version_file), not cwd, so running
        the real file here while chdir'd elsewhere would write into the
        actual checkout instead of tmp_path.
        """
        import runpy

        self._copy_script_into(tmp_path)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("SETUPTOOLS_SCM_PRETEND_VERSION", "9.9.9")

        runpy.run_path(str(tmp_path / "freeze_version.py"), run_name="__main__")

        content = (tmp_path / "solaredge2mqtt" / "_version.py").read_text(
            encoding="utf-8"
        )
        assert "__version__ = version = '9.9.9'" in content
