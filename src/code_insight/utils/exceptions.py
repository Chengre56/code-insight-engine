"""
Custom exception hierarchy for code-insight-engine.

Using a dedicated hierarchy (rather than bare ``Exception`` or built-in
errors) lets callers catch failures at the right granularity -- either
broadly via :class:`CodeInsightError`, or narrowly via a specific
subclass -- and lets the CLI translate failures into clean, actionable
error messages instead of raw tracebacks.
"""

from __future__ import annotations

from pathlib import Path


class CodeInsightError(Exception):
    """Base class for all errors raised by code-insight-engine.

    Catching this exception is sufficient to guard against any
    library-raised failure without needing to enumerate every subclass.
    """


class InvalidPathError(CodeInsightError):
    """Raised when a target path does not exist or is not accessible.

    Args:
        path: The offending filesystem path.
        reason: A short, human-readable explanation of the failure.
    """

    def __init__(self, path: str | Path, reason: str = "path does not exist") -> None:
        self.path = Path(path)
        self.reason = reason
        super().__init__(f"Invalid path '{self.path}': {reason}")


class FileReadError(CodeInsightError):
    """Raised when a source file cannot be read or decoded.

    This typically wraps an underlying ``OSError`` or
    ``UnicodeDecodeError`` so callers get a consistent, library-specific
    exception type regardless of the root cause.

    Args:
        path: The file that failed to read.
        original_error: The underlying exception, if any, for debugging.
    """

    def __init__(self, path: str | Path, original_error: Exception | None = None) -> None:
        self.path = Path(path)
        self.original_error = original_error
        detail = f" ({original_error})" if original_error else ""
        super().__init__(f"Could not read file '{self.path}'{detail}")


class UnsupportedLanguageError(CodeInsightError):
    """Raised when a file extension has no registered language mapping.

    Args:
        path: The file whose extension is unsupported.
        extension: The specific unsupported extension.
    """

    def __init__(self, path: str | Path, extension: str) -> None:
        self.path = Path(path)
        self.extension = extension
        super().__init__(
            f"Unsupported file type '{extension}' for '{self.path}'. "
            "No language mapping registered."
        )
