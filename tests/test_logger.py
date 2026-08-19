"""Tests for code_insight.utils.logger and additional config validation coverage."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import pytest

from code_insight.core.config import AnalysisConfig
from code_insight.utils.logger import get_logger


class TestLoggerBasics:
    def test_returns_same_logger_instance_on_repeat_calls(self) -> None:
        first = get_logger("code_insight.test.repeat")
        second = get_logger("code_insight.test.repeat")
        assert first is second
        assert len(first.handlers) == 1  # no duplicate handlers attached

    def test_verbose_sets_debug_level(self) -> None:
        logger = get_logger("code_insight.test.verbose", verbose=True)
        assert logger.level == logging.DEBUG

    def test_non_verbose_sets_info_level(self) -> None:
        logger = get_logger("code_insight.test.quiet", verbose=False)
        assert logger.level == logging.INFO


class TestJsonLogging:
    def test_json_env_var_produces_json_formatter(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CODE_INSIGHT_LOG_JSON", "1")
        logger = get_logger("code_insight.test.json_console")
        formatter = logger.handlers[0].formatter
        assert formatter is not None

        record = logging.LogRecord(
            name="x", level=logging.INFO, pathname="", lineno=0,
            msg="hello world", args=(), exc_info=None,
        )
        formatted = formatter.format(record)
        parsed = json.loads(formatted)
        assert parsed["message"] == "hello world"
        assert parsed["level"] == "INFO"


class TestFileLogging:
    def test_file_env_var_writes_log_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        log_file = tmp_path / "test.log"
        monkeypatch.setenv("CODE_INSIGHT_LOG_FILE", str(log_file))

        logger = get_logger("code_insight.test.file_logging")
        logger.info("a message that should land in the file")
        for handler in logger.handlers:
            handler.flush()

        assert log_file.exists()
        content = log_file.read_text(encoding="utf-8")
        assert "a message that should land in the file" in content

    def test_file_logging_respects_json_format(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        log_file = tmp_path / "test.jsonl"
        monkeypatch.setenv("CODE_INSIGHT_LOG_FILE", str(log_file))
        monkeypatch.setenv("CODE_INSIGHT_LOG_JSON", "1")

        logger = get_logger("code_insight.test.file_json_logging")
        logger.info("structured line")
        for handler in logger.handlers:
            handler.flush()

        line = log_file.read_text(encoding="utf-8").strip().splitlines()[0]
        parsed = json.loads(line)
        assert parsed["message"] == "structured line"


class TestConfigInputValidation:
    def test_negative_complexity_threshold_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="complexity_threshold"):
            AnalysisConfig(target_path=tmp_path, complexity_threshold=-1)

    def test_zero_complexity_threshold_allowed(self, tmp_path: Path) -> None:
        config = AnalysisConfig(target_path=tmp_path, complexity_threshold=0)
        assert config.complexity_threshold == 0

    def test_empty_exclude_pattern_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="exclude_patterns"):
            AnalysisConfig(target_path=tmp_path, exclude_patterns=("",))

    def test_whitespace_only_exclude_pattern_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="exclude_patterns"):
            AnalysisConfig(target_path=tmp_path, exclude_patterns=("   ",))
