"""
code-insight-engine
====================

A high-performance, multi-language static analysis engine that computes
code quality metrics such as lines of code, comment density, cyclomatic
complexity, and structural counts (functions/classes) across a codebase.

Public API
----------
The package exposes its primary building blocks at the top level for
convenient programmatic use:

    >>> from code_insight import CodeParser, MetricsAggregator, AnalysisConfig
    >>> config = AnalysisConfig(target_path="./my_project")
    >>> parser = CodeParser(config)
    >>> results = [parser.parse_file(f) for f in config.discover_files()]
    >>> project_metrics = MetricsAggregator().aggregate(results, config)

See the CLI entry point (`code-insight analyze --help`) for command-line
usage.
"""

from code_insight.analyzers.metrics import MetricsAggregator, ProjectMetrics
from code_insight.analyzers.parser import CodeParser, FileMetrics
from code_insight.core.config import AnalysisConfig

__version__ = "1.0.0"
__author__ = "DataFactor Engineering"

__all__ = [
    "__version__",
    "AnalysisConfig",
    "CodeParser",
    "FileMetrics",
    "MetricsAggregator",
    "ProjectMetrics",
]
