"""
Professional logging utility for code-insight-engine.

Provides a single :func:`get_logger` factory that returns a consistently
configured :class:`logging.Logger`, with optional ANSI color coding for
terminal output (auto-disabled when output is not a TTY, e.g. when piped
to a file or CI log collector).
"""

from __future__ import annotations

import logging
import sys
from typing import ClassVar

_CONFIGURED_LOGGERS: set[str] = set()


class _ColorFormatter(logging.Formatter):
    """A `logging.Formatter` that adds ANSI colors per log level.

    Colors are only applied when the destination stream is a real
    terminal, so redirected/piped output remains clean plain text.
    """

    _COLORS: ClassVar[dict[int, str]] = {
        logging.DEBUG: "\033[36m",  # cyan
        logging.INFO: "\033[32m",  # green
        logging.WARNING: "\033[33m",  # yellow
        logging.ERROR: "\033[31m",  # red
        logging.CRITICAL: "\033[1;31m",  # bold red
    }
    _RESET = "\033[0m"

    def __init__(self, use_color: bool) -> None:
        super().__init__(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        self._use_color = use_color

    def format(self, record: logging.LogRecord) -> str:
        message = super().format(record)
        if not self._use_color:
            return message
        color = self._COLORS.get(record.levelno, "")
        return f"{color}{message}{self._RESET}" if color else message


def get_logger(name: str, verbose: bool = False) -> logging.Logger:
    """Return a configured logger for the given module/component name.

    Repeated calls with the same ``name`` return the same underlying
    logger without attaching duplicate handlers, so this is safe to call
    from module scope (``logger = get_logger(__name__)``).

    Args:
        name: Logical name of the logger, conventionally ``__name__``.
        verbose: If True, sets the logger to ``DEBUG`` level; otherwise
            ``INFO``. Only applied the first time a given logger name is
            configured.

    Returns:
        A ready-to-use ``logging.Logger`` instance.
    """
    logger = logging.getLogger(name)

    if name not in _CONFIGURED_LOGGERS:
        handler = logging.StreamHandler(stream=sys.stderr)
        use_color = hasattr(sys.stderr, "isatty") and sys.stderr.isatty()
        handler.setFormatter(_ColorFormatter(use_color=use_color))
        logger.addHandler(handler)
        logger.propagate = False
        _CONFIGURED_LOGGERS.add(name)

    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    return logger
