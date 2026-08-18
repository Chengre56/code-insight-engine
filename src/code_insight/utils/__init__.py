"""Shared utilities: logging and exception hierarchy."""

from code_insight.utils.exceptions import (
    CodeInsightError,
    FileReadError,
    InvalidPathError,
    UnsupportedLanguageError,
)
from code_insight.utils.logger import get_logger

__all__ = [
    "CodeInsightError",
    "FileReadError",
    "InvalidPathError",
    "UnsupportedLanguageError",
    "get_logger",
]
