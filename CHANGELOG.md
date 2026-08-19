# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-08-19

### Added
- Initial release of `code-insight-engine`.
- Multi-language static analysis: Python (exact AST-based), plus
  lexical/regex-based analysis for JavaScript, TypeScript, Java, C, C++, C#,
  Go, Rust, Ruby, PHP, Swift, and Kotlin.
- Metrics: lines of code (total/code/comment/blank), comment density,
  cyclomatic complexity (per-function for Python), function/class counts.
- Project-level aggregation: per-language rollups, complexity hotspot
  detection with configurable threshold.
- `code-insight analyze` CLI with `table`, `json`, and `summary` output
  formats, language/exclude filtering, and `--fail-on-hotspot` for CI gating.
- Full test suite (pytest) covering config/discovery, parser edge cases,
  aggregation, and CLI integration.
- GitHub Actions CI: ruff lint, mypy strict type-check, pytest with coverage,
  across Python 3.10–3.12.
