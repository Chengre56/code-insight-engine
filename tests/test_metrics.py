"""Tests for code_insight.analyzers.metrics."""

from __future__ import annotations

from pathlib import Path

from code_insight.analyzers.metrics import MetricsAggregator, ReportFormatter
from code_insight.analyzers.parser import CodeParser
from code_insight.core.config import AnalysisConfig


class TestMetricsAggregator:
    def test_aggregate_basic_counts(self, sample_project: Path) -> None:
        config = AnalysisConfig(target_path=sample_project, complexity_threshold=1)
        files = list(config.discover_files())
        parser = CodeParser()
        results = [parser.parse_file(f) for f in files]

        project = MetricsAggregator().aggregate(results, config)

        assert project.total_files == len(files) - project.error_count
        assert project.error_count == 1  # broken.py has a syntax error
        assert "Python" in project.by_language
        assert "JavaScript" in project.by_language

    def test_by_language_rollup_excludes_errored_files(self, sample_project: Path) -> None:
        config = AnalysisConfig(target_path=sample_project)
        files = list(config.discover_files())
        parser = CodeParser()
        results = [parser.parse_file(f) for f in files]

        project = MetricsAggregator().aggregate(results, config)

        python_summary = project.by_language["Python"]
        # broken.py should not be counted in the language rollup.
        assert python_summary.file_count == sum(
            1 for r in results if r.language == "Python" and r.error is None
        )

    def test_hotspots_respect_threshold(self, sample_project: Path) -> None:
        config = AnalysisConfig(target_path=sample_project, complexity_threshold=1000)
        files = list(config.discover_files())
        parser = CodeParser()
        results = [parser.parse_file(f) for f in files]

        project = MetricsAggregator().aggregate(results, config)

        assert project.hotspots == []

    def test_hotspots_sorted_descending(self, tmp_path: Path) -> None:
        low = tmp_path / "low.py"
        low.write_text("def f():\n    return 1\n", encoding="utf-8")
        high = tmp_path / "high.py"
        high.write_text(
            "def f(x):\n"
            "    if x == 1:\n"
            "        return 1\n"
            "    elif x == 2:\n"
            "        return 2\n"
            "    elif x == 3:\n"
            "        return 3\n"
            "    return 0\n",
            encoding="utf-8",
        )

        config = AnalysisConfig(target_path=tmp_path, complexity_threshold=1)
        parser = CodeParser()
        results = [parser.parse_file(f) for f in [low, high]]
        project = MetricsAggregator().aggregate(results, config)

        assert project.hotspots[0].file_path == high

    def test_empty_input_produces_zeroed_project(self, tmp_path: Path) -> None:
        config = AnalysisConfig(target_path=tmp_path)
        project = MetricsAggregator().aggregate([], config)

        assert project.total_files == 0
        assert project.total_lines == 0
        assert project.average_complexity == 0.0
        assert project.hotspots == []


class TestReportFormatter:
    def test_format_table_contains_key_sections(self, sample_project: Path) -> None:
        config = AnalysisConfig(target_path=sample_project, complexity_threshold=1)
        files = list(config.discover_files())
        parser = CodeParser()
        results = [parser.parse_file(f) for f in files]
        project = MetricsAggregator().aggregate(results, config)

        table = ReportFormatter.format_table(project)

        assert "CODE INSIGHT ENGINE" in table
        assert "BY LANGUAGE" in table
        assert "Files analyzed" in table

    def test_format_summary_is_single_line(self, sample_project: Path) -> None:
        config = AnalysisConfig(target_path=sample_project)
        files = list(config.discover_files())
        parser = CodeParser()
        results = [parser.parse_file(f) for f in files]
        project = MetricsAggregator().aggregate(results, config)

        summary = ReportFormatter.format_summary(project)

        assert "\n" not in summary
        assert "files" in summary

    def test_to_dict_round_trips_key_fields(self, sample_project: Path) -> None:
        config = AnalysisConfig(target_path=sample_project)
        files = list(config.discover_files())
        parser = CodeParser()
        results = [parser.parse_file(f) for f in files]
        project = MetricsAggregator().aggregate(results, config)

        data = project.to_dict()

        assert data["summary"]["total_files"] == project.total_files
        assert set(data.keys()) == {"summary", "by_language", "hotspots", "files"}
