"""
Command-line interface for code-insight-engine.

Exposes a single ``code-insight`` executable (installed via the
``project.scripts`` entry point in ``pyproject.toml``) with an ``analyze``
subcommand. Designed to be both a friendly interactive tool and a
CI-friendly one: ``--format json`` gives machine-readable output, and
``--fail-on-hotspot`` gives a non-zero exit code for pipeline gating.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

from code_insight import __version__
from code_insight.analyzers.metrics import MetricsAggregator, ProjectMetrics, ReportFormatter
from code_insight.analyzers.parser import CodeParser
from code_insight.core.config import AnalysisConfig
from code_insight.utils.exceptions import CodeInsightError
from code_insight.utils.logger import get_logger

logger = get_logger("code_insight.cli")


@click.group()
@click.version_option(version=__version__, prog_name="code-insight")
def cli() -> None:
    """code-insight-engine: multi-language static code analysis.

    Run `code-insight analyze --help` to see analysis options.
    """


@cli.command()
@click.argument("path", type=click.Path(exists=False, path_type=str))
@click.option(
    "--recursive/--no-recursive",
    default=True,
    help="Recurse into subdirectories. [default: recursive]",
)
@click.option(
    "-l",
    "--language",
    "languages",
    multiple=True,
    help="Restrict analysis to one or more languages (repeatable), e.g. -l Python -l Go.",
)
@click.option(
    "-x",
    "--exclude",
    "exclude_patterns",
    multiple=True,
    help="Glob pattern to exclude (repeatable), e.g. -x '*_test.py' -x 'vendor/*'.",
)
@click.option(
    "-f",
    "--format",
    "output_format",
    type=click.Choice(["table", "json", "summary"], case_sensitive=False),
    default="table",
    show_default=True,
    help="Output format.",
)
@click.option(
    "-o",
    "--output",
    "output_file",
    type=click.Path(path_type=str),
    default=None,
    help="Write the report to a file instead of stdout.",
)
@click.option(
    "-c",
    "--complexity-threshold",
    type=int,
    default=10,
    show_default=True,
    help="Cyclomatic complexity at/above which a file is flagged as a hotspot.",
)
@click.option(
    "--fail-on-hotspot",
    is_flag=True,
    default=False,
    help="Exit with status code 2 if any complexity hotspots are found (useful in CI).",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    default=False,
    help="Enable debug-level logging.",
)
def analyze(
    path: str,
    recursive: bool,
    languages: tuple[str, ...],
    exclude_patterns: tuple[str, ...],
    output_format: str,
    output_file: str | None,
    complexity_threshold: int,
    fail_on_hotspot: bool,
    verbose: bool,
) -> None:
    """Analyze PATH (a file or directory) and report code quality metrics.

    \b
    Examples:
      code-insight analyze ./src
      code-insight analyze ./src -l Python -f json -o report.json
      code-insight analyze . -x 'tests/*' -c 15 --fail-on-hotspot
    """
    if verbose:
        logger.setLevel("DEBUG")

    config = AnalysisConfig(
        target_path=path,
        recursive=recursive,
        languages=frozenset(languages),
        exclude_patterns=exclude_patterns,
        complexity_threshold=complexity_threshold,
    )

    try:
        config.validate()
    except CodeInsightError as exc:
        logger.error(str(exc))
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    parser = CodeParser()
    logger.info("Discovering files under %s", config.target_path)
    discovered = list(config.discover_files())

    if not discovered:
        message = "No analyzable files found for the given path/filters."
        logger.warning(message)
        click.echo(message)
        sys.exit(0)

    logger.info("Analyzing %d file(s)...", len(discovered))
    file_metrics = [parser.parse_file(f) for f in discovered]

    project = MetricsAggregator().aggregate(file_metrics, config)
    logger.info(
        "Analysis complete: %d files, %d error(s), %d hotspot(s)",
        project.total_files,
        project.error_count,
        len(project.hotspots),
    )

    report = _render_report(project, output_format)
    _emit_report(report, output_file)

    if fail_on_hotspot and project.hotspots:
        click.echo(
            f"\n{len(project.hotspots)} complexity hotspot(s) at/above threshold "
            f"{complexity_threshold}.",
            err=True,
        )
        sys.exit(2)


def _render_report(project: ProjectMetrics, output_format: str) -> str:
    """Render the aggregated project metrics in the requested format."""
    if output_format == "json":
        return json.dumps(project.to_dict(), indent=2, default=str)
    if output_format == "summary":
        return ReportFormatter.format_summary(project)
    return ReportFormatter.format_table(project)


def _emit_report(report: str, output_file: str | None) -> None:
    """Write the report to stdout, or to a file if requested."""
    if output_file is None:
        click.echo(report)
        return

    out_path = Path(output_file).expanduser().resolve()
    try:
        out_path.write_text(report, encoding="utf-8")
    except OSError as exc:
        logger.error("Failed to write report to %s: %s", out_path, exc)
        click.echo(f"Error: could not write to '{out_path}': {exc}", err=True)
        sys.exit(1)
    click.echo(f"Report written to {out_path}")


def main() -> None:
    """Console-script entry point (used by `python -m code_insight`)."""
    cli()


if __name__ == "__main__":
    main()
