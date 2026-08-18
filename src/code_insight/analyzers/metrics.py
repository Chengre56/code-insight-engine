"""
Project-level metrics aggregation and presentation.

Takes the per-file :class:`~code_insight.analyzers.parser.FileMetrics`
produced by :class:`~code_insight.analyzers.parser.CodeParser` and rolls
them up into a single :class:`ProjectMetrics` summary: totals, per-language
breakdowns, and a ranked list of "complexity hotspots" worth reviewing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from code_insight.analyzers.parser import FileMetrics
from code_insight.core.config import AnalysisConfig


@dataclass
class LanguageSummary:
    """Aggregated metrics for a single language across the project.

    Attributes:
        language: Language name.
        file_count: Number of files of this language analyzed.
        total_lines: Sum of total lines across those files.
        code_lines: Sum of code lines.
        comment_lines: Sum of comment lines.
        blank_lines: Sum of blank lines.
        function_count: Sum of function/method counts.
        class_count: Sum of class/struct/interface counts.
        cyclomatic_complexity: Sum of file-level complexity scores.
    """

    language: str
    file_count: int = 0
    total_lines: int = 0
    code_lines: int = 0
    comment_lines: int = 0
    blank_lines: int = 0
    function_count: int = 0
    class_count: int = 0
    cyclomatic_complexity: int = 0

    @property
    def comment_density(self) -> float:
        """Aggregate comment density for this language."""
        return self.comment_lines / self.total_lines if self.total_lines else 0.0

    def to_dict(self) -> dict[str, object]:
        """Serialize to a JSON-friendly dictionary."""
        return {
            "language": self.language,
            "file_count": self.file_count,
            "total_lines": self.total_lines,
            "code_lines": self.code_lines,
            "comment_lines": self.comment_lines,
            "blank_lines": self.blank_lines,
            "comment_density": round(self.comment_density, 4),
            "function_count": self.function_count,
            "class_count": self.class_count,
            "cyclomatic_complexity": self.cyclomatic_complexity,
        }


@dataclass
class ProjectMetrics:
    """Aggregated results for an entire analysis run.

    Attributes:
        files: Per-file metrics, in the order they were analyzed.
        by_language: Per-language rollups, keyed by language name.
        complexity_threshold: The threshold used to compute ``hotspots``.
        error_count: Number of files that failed to parse.
    """

    files: list[FileMetrics] = field(default_factory=list)
    by_language: dict[str, LanguageSummary] = field(default_factory=dict)
    complexity_threshold: int = 10
    error_count: int = 0

    @property
    def total_files(self) -> int:
        """Total number of files successfully analyzed (excludes errors)."""
        return sum(1 for f in self.files if f.error is None)

    @property
    def total_lines(self) -> int:
        return sum(f.total_lines for f in self.files)

    @property
    def total_code_lines(self) -> int:
        return sum(f.code_lines for f in self.files)

    @property
    def total_comment_lines(self) -> int:
        return sum(f.comment_lines for f in self.files)

    @property
    def total_blank_lines(self) -> int:
        return sum(f.blank_lines for f in self.files)

    @property
    def total_functions(self) -> int:
        return sum(f.function_count for f in self.files)

    @property
    def total_classes(self) -> int:
        return sum(f.class_count for f in self.files)

    @property
    def average_comment_density(self) -> float:
        """Mean comment density across all successfully-analyzed files."""
        valid = [f.comment_density for f in self.files if f.error is None and f.total_lines > 0]
        return sum(valid) / len(valid) if valid else 0.0

    @property
    def average_complexity(self) -> float:
        """Mean file-level cyclomatic complexity across analyzed files."""
        valid = [f.cyclomatic_complexity for f in self.files if f.error is None]
        return sum(valid) / len(valid) if valid else 0.0

    @property
    def hotspots(self) -> list[FileMetrics]:
        """Files whose complexity meets or exceeds ``complexity_threshold``.

        Sorted descending by cyclomatic complexity so the worst offenders
        appear first.
        """
        flagged = [
            f
            for f in self.files
            if f.error is None and f.cyclomatic_complexity >= self.complexity_threshold
        ]
        return sorted(flagged, key=lambda f: f.cyclomatic_complexity, reverse=True)

    def to_dict(self) -> dict[str, object]:
        """Serialize the full report to a JSON-friendly dictionary."""
        return {
            "summary": {
                "total_files": self.total_files,
                "error_count": self.error_count,
                "total_lines": self.total_lines,
                "total_code_lines": self.total_code_lines,
                "total_comment_lines": self.total_comment_lines,
                "total_blank_lines": self.total_blank_lines,
                "total_functions": self.total_functions,
                "total_classes": self.total_classes,
                "average_comment_density": round(self.average_comment_density, 4),
                "average_complexity": round(self.average_complexity, 4),
                "complexity_threshold": self.complexity_threshold,
            },
            "by_language": {name: summary.to_dict() for name, summary in self.by_language.items()},
            "hotspots": [f.to_dict() for f in self.hotspots],
            "files": [f.to_dict() for f in self.files],
        }


class MetricsAggregator:
    """Rolls up per-file metrics into a :class:`ProjectMetrics` summary."""

    def aggregate(self, file_metrics: list[FileMetrics], config: AnalysisConfig) -> ProjectMetrics:
        """Aggregate a list of per-file metrics into a project summary.

        Args:
            file_metrics: Results from :meth:`CodeParser.parse_file`, one
                per analyzed file.
            config: The configuration used for the run (supplies the
                complexity threshold used to compute hotspots).

        Returns:
            A populated :class:`ProjectMetrics`.
        """
        project = ProjectMetrics(
            files=list(file_metrics), complexity_threshold=config.complexity_threshold
        )
        project.error_count = sum(1 for f in file_metrics if f.error is not None)

        by_language: dict[str, LanguageSummary] = {}
        for fm in file_metrics:
            if fm.error is not None:
                continue
            summary = by_language.setdefault(fm.language, LanguageSummary(language=fm.language))
            summary.file_count += 1
            summary.total_lines += fm.total_lines
            summary.code_lines += fm.code_lines
            summary.comment_lines += fm.comment_lines
            summary.blank_lines += fm.blank_lines
            summary.function_count += fm.function_count
            summary.class_count += fm.class_count
            summary.cyclomatic_complexity += fm.cyclomatic_complexity

        project.by_language = by_language
        return project


class ReportFormatter:
    """Renders a :class:`ProjectMetrics` as human-readable text output."""

    @staticmethod
    def format_table(project: ProjectMetrics) -> str:
        """Render a plain-text summary table (no external dependencies).

        Args:
            project: The aggregated project metrics to render.

        Returns:
            A multi-section formatted string suitable for terminal output.
        """
        lines: list[str] = []
        lines.append("=" * 70)
        lines.append(" CODE INSIGHT ENGINE - ANALYSIS REPORT")
        lines.append("=" * 70)
        lines.append(f"Files analyzed     : {project.total_files}")
        if project.error_count:
            lines.append(f"Files with errors  : {project.error_count}")
        lines.append(f"Total lines        : {project.total_lines}")
        lines.append(f"Code lines         : {project.total_code_lines}")
        lines.append(f"Comment lines      : {project.total_comment_lines}")
        lines.append(f"Blank lines        : {project.total_blank_lines}")
        lines.append(f"Functions          : {project.total_functions}")
        lines.append(f"Classes            : {project.total_classes}")
        lines.append(f"Avg comment density: {project.average_comment_density:.1%}")
        lines.append(f"Avg complexity     : {project.average_complexity:.2f}")

        if project.by_language:
            lines.append("")
            lines.append("-" * 70)
            lines.append(" BY LANGUAGE")
            lines.append("-" * 70)
            header = (
                f"{'Language':<14}{'Files':>8}{'Lines':>10}"
                f"{'Funcs':>8}{'Classes':>9}{'Complexity':>12}"
            )
            lines.append(header)
            by_lines = sorted(
                project.by_language.values(), key=lambda s: s.total_lines, reverse=True
            )
            for summary in by_lines:
                lines.append(
                    f"{summary.language:<14}{summary.file_count:>8}{summary.total_lines:>10}"
                    f"{summary.function_count:>8}{summary.class_count:>9}"
                    f"{summary.cyclomatic_complexity:>12}"
                )

        hotspots = project.hotspots
        if hotspots:
            lines.append("")
            lines.append("-" * 70)
            lines.append(f" COMPLEXITY HOTSPOTS (threshold >= {project.complexity_threshold})")
            lines.append("-" * 70)
            for fm in hotspots[:20]:
                lines.append(f"  [{fm.cyclomatic_complexity:>4}] {fm.file_path}")
            if len(hotspots) > 20:
                lines.append(f"  ... and {len(hotspots) - 20} more")

        lines.append("=" * 70)
        return "\n".join(lines)

    @staticmethod
    def format_summary(project: ProjectMetrics) -> str:
        """Render a single-line summary, useful for CI logs or quick checks."""
        return (
            f"{project.total_files} files, {project.total_lines} lines, "
            f"{project.total_functions} functions, "
            f"avg complexity {project.average_complexity:.2f}, "
            f"{len(project.hotspots)} hotspot(s) at threshold {project.complexity_threshold}"
        )
