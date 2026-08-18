"""Tests for code_insight.core.config."""

from __future__ import annotations

from pathlib import Path

import pytest

from code_insight.core.config import AnalysisConfig, detect_language
from code_insight.utils.exceptions import InvalidPathError


class TestDetectLanguage:
    def test_python_extension(self) -> None:
        spec = detect_language(Path("foo.py"))
        assert spec is not None
        assert spec.name == "Python"

    def test_typescript_extension(self) -> None:
        spec = detect_language(Path("component.tsx"))
        assert spec is not None
        assert spec.name == "TypeScript"

    def test_unknown_extension_returns_none(self) -> None:
        assert detect_language(Path("data.unknownext")) is None

    def test_case_insensitive(self) -> None:
        spec = detect_language(Path("Main.PY"))
        assert spec is not None
        assert spec.name == "Python"


class TestAnalysisConfigValidation:
    def test_validate_raises_for_missing_path(self, tmp_path: Path) -> None:
        config = AnalysisConfig(target_path=tmp_path / "does_not_exist")
        with pytest.raises(InvalidPathError):
            config.validate()

    def test_validate_passes_for_existing_path(self, tmp_path: Path) -> None:
        config = AnalysisConfig(target_path=tmp_path)
        config.validate()  # should not raise

    def test_target_path_is_resolved_absolute(self, tmp_path: Path) -> None:
        config = AnalysisConfig(target_path=str(tmp_path))
        assert Path(config.target_path).is_absolute()


class TestDiscoverFiles:
    def test_discovers_known_languages_only(self, sample_project: Path) -> None:
        config = AnalysisConfig(target_path=sample_project)
        found = {p.name for p in config.discover_files()}
        assert "main.py" in found
        assert "app.js" in found
        assert "README.md" not in found  # unsupported extension

    def test_excludes_default_directories(self, sample_project: Path) -> None:
        config = AnalysisConfig(target_path=sample_project)
        found = {p.name for p in config.discover_files()}
        assert "lib.js" not in found  # inside node_modules

    def test_language_filter(self, sample_project: Path) -> None:
        config = AnalysisConfig(target_path=sample_project, languages=frozenset({"python"}))
        found = {p.suffix for p in config.discover_files()}
        assert found == {".py"}

    def test_custom_exclude_pattern(self, sample_project: Path) -> None:
        config = AnalysisConfig(target_path=sample_project, exclude_patterns=("main.py",))
        found = {p.name for p in config.discover_files()}
        assert "main.py" not in found

    def test_non_recursive_skips_subdirectories(self, sample_project: Path) -> None:
        config = AnalysisConfig(target_path=sample_project, recursive=False)
        found = {p.name for p in config.discover_files()}
        assert "main.py" not in found  # lives under pkg/
        assert "app.js" in found  # top-level

    def test_single_file_target(self, sample_project: Path) -> None:
        config = AnalysisConfig(target_path=sample_project / "app.js")
        found = list(config.discover_files())
        assert len(found) == 1
        assert found[0].name == "app.js"

    def test_raises_for_missing_target(self, tmp_path: Path) -> None:
        config = AnalysisConfig(target_path=tmp_path / "nope")
        with pytest.raises(InvalidPathError):
            list(config.discover_files())
