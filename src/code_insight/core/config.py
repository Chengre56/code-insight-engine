"""
Configuration and path management for code-insight-engine.

This module owns two responsibilities:

1. **Language registry** -- a static mapping of file extensions to
   language identifiers and their comment syntax, used by the parser to
   decide *how* to analyze a file.
2. **AnalysisConfig / PathManager** -- resolves and validates the
   user-supplied target path, applies include/exclude filtering, and
   walks the filesystem to discover analyzable files.

Keeping this logic centralized means the CLI, the parser, and any future
programmatic caller share a single, well-tested source of truth for
"which files get analyzed and how".
"""

from __future__ import annotations

import fnmatch
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from code_insight.utils.exceptions import InvalidPathError

# --------------------------------------------------------------------------- #
# Language registry
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class LanguageSpec:
    """Describes how to recognize and lexically analyze a language.

    Attributes:
        name: Human-readable language identifier (e.g. ``"Python"``).
        line_comment: Token(s) that start a single-line comment.
        block_comment_start: Token that opens a block comment, if any.
        block_comment_end: Token that closes a block comment, if any.
    """

    name: str
    line_comment: tuple[str, ...]
    block_comment_start: str | None = None
    block_comment_end: str | None = None


# Extension -> LanguageSpec. This is the single source of truth for
# "which languages does code-insight-engine understand".
def _c_style(name: str, *, line: tuple[str, ...] = ("//",)) -> LanguageSpec:
    """Shorthand for the common "C-style" `// line` + `/* block */` comment syntax."""
    return LanguageSpec(name, line_comment=line, block_comment_start="/*", block_comment_end="*/")


LANGUAGE_REGISTRY: dict[str, LanguageSpec] = {
    ".py": LanguageSpec(
        "Python", line_comment=("#",), block_comment_start='"""', block_comment_end='"""'
    ),
    ".pyi": LanguageSpec("Python", line_comment=("#",)),
    ".js": _c_style("JavaScript"),
    ".jsx": _c_style("JavaScript"),
    ".mjs": _c_style("JavaScript"),
    ".ts": _c_style("TypeScript"),
    ".tsx": _c_style("TypeScript"),
    ".java": _c_style("Java"),
    ".c": _c_style("C"),
    ".h": _c_style("C"),
    ".cpp": _c_style("C++"),
    ".hpp": _c_style("C++"),
    ".cs": _c_style("C#"),
    ".go": _c_style("Go"),
    ".rs": _c_style("Rust"),
    ".rb": LanguageSpec(
        "Ruby", line_comment=("#",), block_comment_start="=begin", block_comment_end="=end"
    ),
    ".php": _c_style("PHP", line=("//", "#")),
    ".swift": _c_style("Swift"),
    ".kt": _c_style("Kotlin"),
}

# Directories that are near-universally uninteresting for source analysis.
DEFAULT_EXCLUDE_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".tox",
        ".venv",
        "venv",
        "env",
        "node_modules",
        "dist",
        "build",
        ".eggs",
        "*.egg-info",
        ".idea",
        ".vscode",
        "htmlcov",
    }
)


def detect_language(path: Path) -> LanguageSpec | None:
    """Look up the :class:`LanguageSpec` for a file, or ``None`` if unknown.

    Args:
        path: File path whose suffix should be resolved.

    Returns:
        The matching ``LanguageSpec``, or ``None`` if the extension is
        not registered.
    """
    return LANGUAGE_REGISTRY.get(path.suffix.lower())


# --------------------------------------------------------------------------- #
# Configuration + discovery
# --------------------------------------------------------------------------- #


@dataclass
class AnalysisConfig:
    """Holds all user-tunable parameters for a single analysis run.

    Attributes:
        target_path: File or directory to analyze.
        recursive: Whether to descend into subdirectories.
        languages: If non-empty, restrict analysis to these language
            names (case-insensitive), e.g. ``{"Python", "Go"}``.
        exclude_patterns: Additional glob patterns (matched against file
            name and path components) to skip, layered on top of
            :data:`DEFAULT_EXCLUDE_DIRS`.
        complexity_threshold: Cyclomatic complexity value at or above
            which a function/file is flagged as a "hotspot".
        use_default_excludes: Whether to apply :data:`DEFAULT_EXCLUDE_DIRS`
            in addition to ``exclude_patterns``.
    """

    target_path: str | Path
    recursive: bool = True
    languages: frozenset[str] = field(default_factory=frozenset)
    exclude_patterns: tuple[str, ...] = field(default_factory=tuple)
    complexity_threshold: int = 10
    use_default_excludes: bool = True

    def __post_init__(self) -> None:
        self.target_path = Path(self.target_path).expanduser().resolve()
        # Normalize language filters to lowercase for case-insensitive matching.
        self.languages = frozenset(lang.lower() for lang in self.languages)

    def validate(self) -> None:
        """Ensure the target path exists.

        Raises:
            InvalidPathError: If ``target_path`` does not exist on disk.
        """
        if not Path(self.target_path).exists():
            raise InvalidPathError(self.target_path, reason="path does not exist")

    def _is_excluded_dir(self, dir_name: str) -> bool:
        if not self.use_default_excludes:
            return False
        return any(fnmatch.fnmatch(dir_name, pattern) for pattern in DEFAULT_EXCLUDE_DIRS)

    def _is_excluded_file(self, file_path: Path) -> bool:
        parts = file_path.parts
        for pattern in self.exclude_patterns:
            if fnmatch.fnmatch(file_path.name, pattern) or fnmatch.fnmatch(str(file_path), pattern):
                return True
            if any(fnmatch.fnmatch(part, pattern) for part in parts):
                return True
        return False

    def _language_allowed(self, path: Path) -> bool:
        spec = detect_language(path)
        if spec is None:
            return False
        if not self.languages:
            return True
        return spec.name.lower() in self.languages

    def discover_files(self) -> Iterator[Path]:
        """Yield all analyzable files under ``target_path``.

        Applies directory exclusions, user-supplied glob excludes, and
        language filtering. A single file target is yielded directly
        (subject to the same filters) rather than walked.

        Raises:
            InvalidPathError: If ``target_path`` does not exist.

        Yields:
            Resolved ``Path`` objects for each file to analyze.
        """
        self.validate()
        target = Path(self.target_path)

        if target.is_file():
            if self._language_allowed(target) and not self._is_excluded_file(target):
                yield target
            return

        if self.recursive:
            walker = target.rglob("*")
        else:
            walker = target.glob("*")

        for candidate in walker:
            if candidate.is_dir():
                continue
            relative_parts = candidate.relative_to(target).parts[:-1]
            if any(self._is_excluded_dir(part) for part in relative_parts):
                continue
            if self._is_excluded_file(candidate):
                continue
            if not self._language_allowed(candidate):
                continue
            yield candidate
