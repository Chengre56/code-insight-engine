"""Integration tests for the code-insight CLI."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from code_insight.core.cli import cli


class TestAnalyzeCommand:
    def test_analyze_table_output(self, sample_project: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", str(sample_project)])

        assert result.exit_code == 0
        assert "CODE INSIGHT ENGINE" in result.output

    def test_analyze_json_output_is_valid_json(self, sample_project: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", str(sample_project), "--format", "json"])

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert "summary" in payload
        assert payload["summary"]["total_files"] > 0

    def test_analyze_summary_output(self, sample_project: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", str(sample_project), "--format", "summary"])

        assert result.exit_code == 0
        assert "files" in result.output

    def test_analyze_invalid_path_exits_nonzero(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", str(tmp_path / "nope")])

        assert result.exit_code == 1
        assert "Error" in result.output

    def test_analyze_language_filter(self, sample_project: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli, ["analyze", str(sample_project), "-l", "Python", "--format", "json"]
        )

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert list(payload["by_language"].keys()) == ["Python"]

    def test_analyze_writes_output_file(self, sample_project: Path, tmp_path: Path) -> None:
        out_file = tmp_path / "report.txt"
        runner = CliRunner()
        result = runner.invoke(
            cli, ["analyze", str(sample_project), "-o", str(out_file)]
        )

        assert result.exit_code == 0
        assert out_file.exists()
        assert "CODE INSIGHT ENGINE" in out_file.read_text(encoding="utf-8")

    def test_fail_on_hotspot_flag_sets_exit_code(self, sample_project: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "analyze",
                str(sample_project),
                "--complexity-threshold",
                "1",
                "--fail-on-hotspot",
            ],
        )

        assert result.exit_code == 2

    def test_no_matching_files_exits_cleanly(self, tmp_path: Path) -> None:
        (tmp_path / "notes.txt").write_text("nothing to see here", encoding="utf-8")
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", str(tmp_path)])

        assert result.exit_code == 0
        assert "No analyzable files" in result.output

    def test_help_text_available(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", "--help"])

        assert result.exit_code == 0
        assert "Analyze PATH" in result.output

    def test_version_flag(self) -> None:
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])

        assert result.exit_code == 0
        assert "code-insight" in result.output.lower()
