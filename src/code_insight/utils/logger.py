"""
Professional logging utility for code-insight-engine.

Provides a single :func:`get_logger` factory that returns a consistently
configured :class:`logging.Logger`. Supports three independent knobs, each
overridable via environment variable so behavior can be tuned in CI/production
without code changes:

* **Color** -- ANSI-colored console output, auto-disabled on non-TTY streams
  (e.g. when piped to a file or CI log collector).
* **Structured (JSON) logging** -- set ``CODE_INSIGHT_LOG_JSON=1`` to emit
  one-JSON-object-per-line logs instead of human-readable text, for ingestion
  by log aggregators (Datadog, CloudWatch, ELK, etc.).
* **File logging** -- set ``CODE_INSIGHT_LOG_FILE=/path/to/file.log`` to
  additionally write logs to a rotating file handler, independent of console
  output.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import sys
from typing import ClassVar

_CONFIGURED_LOGGERS: set[str] = set()

_ENV_LOG_JSON = "CODE_INSIGHT_LOG_JSON"
_ENV_LOG_FILE = "CODE_INSIGHT_LOG_FILE"
_ENV_LOG_FILE_MAX_BYTES = "CODE_INSIGHT_LOG_FILE_MAX_BYTES"
_DEFAULT_MAX_BYTES = 5 * 1024 * 1024  # 5 MiB per log file before rotation
_BACKUP_COUNT = 3


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


class _JsonFormatter(logging.Formatter):
    """Emits one JSON object per log line for machine ingestion.

    Fields: ``timestamp``, ``level``, ``logger``, ``message``, and
    ``exception`` (present only when the record carries exception info).
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def _build_console_handler(use_json: bool) -> logging.Handler:
    handler = logging.StreamHandler(stream=sys.stderr)
    if use_json:
        handler.setFormatter(_JsonFormatter())
    else:
        use_color = hasattr(sys.stderr, "isatty") and sys.stderr.isatty()
        handler.setFormatter(_ColorFormatter(use_color=use_color))
    return handler


def _build_file_handler(path: str, use_json: bool) -> logging.Handler:
    max_bytes = int(os.environ.get(_ENV_LOG_FILE_MAX_BYTES, _DEFAULT_MAX_BYTES))
    handler = logging.handlers.RotatingFileHandler(
        path, maxBytes=max_bytes, backupCount=_BACKUP_COUNT, encoding="utf-8"
    )
    handler.setFormatter(
        _JsonFormatter()
        if use_json
        else logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    return handler


def get_logger(name: str, verbose: bool = False) -> logging.Logger:
    """Return a configured logger for the given module/component name.

    Repeated calls with the same ``name`` return the same underlying
    logger without attaching duplicate handlers, so this is safe to call
    from module scope (``logger = get_logger(__name__)``).

    Behavior can be tuned via environment variables without code changes:

    * ``CODE_INSIGHT_LOG_JSON=1`` -- emit structured JSON instead of
      human-readable text (applies to both console and file output).
    * ``CODE_INSIGHT_LOG_FILE=/path/to/file.log`` -- additionally log to a
      rotating file (5 MiB per file, 3 backups, configurable via
      ``CODE_INSIGHT_LOG_FILE_MAX_BYTES``).

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
        use_json = os.environ.get(_ENV_LOG_JSON, "").strip() in {"1", "true", "True"}

        logger.addHandler(_build_console_handler(use_json))

        log_file = os.environ.get(_ENV_LOG_FILE, "").strip()
        if log_file:
            logger.addHandler(_build_file_handler(log_file, use_json))

        logger.propagate = False
        _CONFIGURED_LOGGERS.add(name)

    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    return logger
