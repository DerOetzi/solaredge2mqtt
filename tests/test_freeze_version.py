"""Tests for freeze_version.py script."""

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import ANY, patch

import pytest


class TestGenerateVersionJson:
    """Tests for generate_version_json function."""

    def test_writes_version_json(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Test that generate_version_json writes a valid version.json file."""
        monkeypatch.chdir(tmp_path)
        version_file = tmp_path / "solaredge2mqtt" / "version.json"
        version_file.parent.mkdir(parents=True)

        with patch("freeze_version.get_version", return_value="1.2.3") as mock_get:
            from freeze_version import generate_version_json

            generate_version_json()

            mock_get.assert_called_once_with(root=".", relative_to=ANY)

        data = json.loads(version_file.read_text(encoding="utf-8"))
        assert data == {"version": "1.2.3"}

    def test_version_json_ends_with_newline(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Test that the generated version.json file ends with a newline."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "solaredge2mqtt").mkdir()

        with patch("freeze_version.get_version", return_value="0.9.0"):
            from freeze_version import generate_version_json

            generate_version_json()

        content = (tmp_path / "solaredge2mqtt" / "version.json").read_text(
            encoding="utf-8"
        )
        assert content.endswith("\n")

    def test_prints_generated_path(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture,
    ):
        """Test that generate_version_json prints the output path and version."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "solaredge2mqtt").mkdir()

        with patch("freeze_version.get_version", return_value="2.0.0"):
            from freeze_version import generate_version_json

            generate_version_json()

        captured = capsys.readouterr()
        assert "version.json" in captured.out
        assert "2.0.0" in captured.out

    def test_main_block_calls_generate_version_json(self, tmp_path: Path):
        """Test that running freeze_version as __main__ writes the version file."""
        script_copy = tmp_path / "freeze_version.py"
        script_copy.write_text(
            (Path(__file__).parent.parent / "freeze_version.py").read_text(
                encoding="utf-8"
            ),
            encoding="utf-8",
        )
        (tmp_path / "solaredge2mqtt").mkdir()

        result = subprocess.run(
            [sys.executable, "freeze_version.py"],
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
            env={**os.environ, "SETUPTOOLS_SCM_PRETEND_VERSION": "1.2.3"},
        )
        assert result.returncode == 0
        assert "version.json" in result.stdout

        data = json.loads(
            (tmp_path / "solaredge2mqtt" / "version.json").read_text(encoding="utf-8")
        )
        assert data == {"version": "1.2.3"}

    def test_main_block_guard_executes_generate_version_json(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """The if __name__ == '__main__' guard is exercised via runpy."""
        import runpy

        monkeypatch.chdir(tmp_path)
        (tmp_path / "solaredge2mqtt").mkdir()

        with patch("setuptools_scm.get_version", return_value="9.9.9"):
            runpy.run_path(
                str(Path(__file__).parent.parent / "freeze_version.py"),
                run_name="__main__",
            )

        data = json.loads(
            (tmp_path / "solaredge2mqtt" / "version.json").read_text(encoding="utf-8")
        )
        assert data["version"] == "9.9.9"


class TestGenerateVersionJsonIntegration:
    """Integration tests verifying valid JSON structure."""

    def test_version_json_is_valid_json(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Test that the written file is parseable JSON with a 'version' key."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "solaredge2mqtt").mkdir()

        with patch("freeze_version.get_version", return_value="3.1.4"):
            from freeze_version import generate_version_json

            generate_version_json()

        raw = (tmp_path / "solaredge2mqtt" / "version.json").read_text(encoding="utf-8")
        parsed = json.loads(raw)
        assert "version" in parsed
        assert parsed["version"] == "3.1.4"

    def test_version_json_pretty_printed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Test that the file uses indent=2 for pretty printing."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / "solaredge2mqtt").mkdir()

        with patch("freeze_version.get_version", return_value="1.0.0"):
            from freeze_version import generate_version_json

            generate_version_json()

        raw = (tmp_path / "solaredge2mqtt" / "version.json").read_text(encoding="utf-8")
        # indent=2 produces lines like '  "version": ...'
        assert '  "version"' in raw
