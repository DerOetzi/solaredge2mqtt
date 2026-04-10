"""Tests for generate_requirements.py script."""

import subprocess
import sys
from pathlib import Path
from textwrap import dedent

import pytest

WORKSPACE_ROOT = Path(__file__).parent.parent


class TestGenerateRequirements:
    """Tests for generate_requirements.py script."""

    def _run_main(
        self, pyproject_content: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> tuple[Path, Path]:
        """Helper: write pyproject.toml in tmp_path, cd there, and call main()."""
        (tmp_path / "pyproject.toml").write_text(pyproject_content, encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        import importlib

        import generate_requirements

        importlib.reload(generate_requirements)
        generate_requirements.main()

        return tmp_path / "requirements.txt", tmp_path / "requirements-armv7.txt"

    def test_main_dependencies_written_to_both_files(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        content = dedent("""\
            [project]
            dependencies = ["requests>=2.0", "pydantic>=2.0"]
        """)
        req, arm = self._run_main(content, tmp_path, monkeypatch)

        req_lines = req.read_text().splitlines()
        arm_lines = arm.read_text().splitlines()

        assert "requests>=2.0" in req_lines
        assert "pydantic>=2.0" in req_lines
        assert "requests>=2.0" in arm_lines
        assert "pydantic>=2.0" in arm_lines

    def test_forecast_extras_only_in_requirements_txt(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Forecast optional-dependencies only appear in requirements.txt."""
        content = dedent("""\
            [project]
            dependencies = ["requests>=2.0"]

            [project.optional-dependencies]
            forecast = ["scikit-learn>=1.0"]
        """)
        req, arm = self._run_main(content, tmp_path, monkeypatch)

        req_lines = req.read_text().splitlines()
        arm_lines = arm.read_text().splitlines()

        assert "scikit-learn>=1.0" in req_lines
        assert "scikit-learn>=1.0" not in arm_lines

    def test_output_files_are_sorted(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Both output files should be lexicographically sorted."""
        content = dedent("""\
            [project]
            dependencies = ["zlib-ng", "aiohttp>=3"]

            [project.optional-dependencies]
            forecast = ["catboost>=1.0"]
        """)
        req, arm = self._run_main(content, tmp_path, monkeypatch)

        req_lines = [line for line in req.read_text().splitlines() if line]
        arm_lines = [line for line in arm.read_text().splitlines() if line]

        assert req_lines == sorted(req_lines)
        assert arm_lines == sorted(arm_lines)

    def test_output_files_end_with_newline(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Both output files should end with a trailing newline."""
        content = dedent("""\
            [project]
            dependencies = ["requests>=2.0"]
        """)
        req, arm = self._run_main(content, tmp_path, monkeypatch)

        assert req.read_text().endswith("\n")
        assert arm.read_text().endswith("\n")

    def test_empty_dependencies_produces_empty_files(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """With no dependencies, output files contain only the newline."""
        content = dedent("""\
            [project]
            dependencies = []
        """)
        req, arm = self._run_main(content, tmp_path, monkeypatch)

        assert req.read_text() == "\n"
        assert arm.read_text() == "\n"

    def test_no_forecast_section_only_writes_core_deps(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        content = dedent("""\
            [project]
            dependencies = ["httpx>=0.20"]

            [project.optional-dependencies]
            dev = ["pytest"]
        """)
        req, arm = self._run_main(content, tmp_path, monkeypatch)

        assert req.read_text() == arm.read_text()

    def test_prints_success_message(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture,
    ):
        """main() prints a success confirmation message."""
        content = dedent("""\
            [project]
            dependencies = ["anyio"]
        """)
        self._run_main(content, tmp_path, monkeypatch)

        captured = capsys.readouterr()
        assert "requirements" in captured.out.lower()

    def test_deduplication_of_overlapping_deps(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        content = dedent("""\
            [project]
            dependencies = ["numpy>=1.0"]

            [project.optional-dependencies]
            forecast = ["numpy>=1.0", "scikit-learn"]
        """)
        req, _ = self._run_main(content, tmp_path, monkeypatch)

        req_lines = req.read_text().splitlines()
        assert req_lines.count("numpy>=1.0") == 1

    def test_main_block_runs_via_subprocess(self):
        """Running script as __main__ exits with code 0 and prints confirmation."""
        result = subprocess.run(
            [sys.executable, str(WORKSPACE_ROOT / "generate_requirements.py")],
            capture_output=True,
            text=True,
            cwd=str(WORKSPACE_ROOT),
        )
        assert result.returncode == 0
        assert "requirements" in result.stdout.lower()

    def test_main_block_guard_executes_main(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture,
    ):
        """The if __name__ == '__main__' guard is exercised via runpy."""
        import runpy

        (tmp_path / "pyproject.toml").write_text(
            "[project]\ndependencies = []\n", encoding="utf-8"
        )
        monkeypatch.chdir(tmp_path)

        runpy.run_path(
            str(WORKSPACE_ROOT / "generate_requirements.py"),
            run_name="__main__",
        )

        assert (tmp_path / "requirements.txt").exists()
