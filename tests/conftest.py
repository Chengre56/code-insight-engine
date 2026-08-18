"""Shared pytest fixtures for code-insight-engine tests."""

from __future__ import annotations

from pathlib import Path

import pytest

SAMPLE_PYTHON = '''\
"""Sample module docstring."""

import os  # inline comment


def add(a, b):
    # simple function, complexity 1
    return a + b


def classify(value):
    if value < 0:
        return "negative"
    elif value == 0:
        return "zero"
    else:
        for i in range(value):
            if i % 2 == 0:
                continue
        return "positive"


class Widget:
    """A widget."""

    def __init__(self, name):
        self.name = name

    def describe(self):
        try:
            return f"Widget: {self.name}"
        except Exception:
            return "unknown"
'''

SAMPLE_JS = """\
// header comment
function add(a, b) {
    return a + b;
}

const classify = (value) => {
    if (value < 0) {
        return "negative";
    } else if (value === 0) {
        return "zero";
    }
    return "positive";
};

class Widget {
    constructor(name) {
        this.name = name;
    }
}
"""

SAMPLE_BROKEN_PYTHON = "def broken(:\n    pass\n"


@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    """Create a small multi-language project tree for integration tests."""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "pkg" / "main.py").write_text(SAMPLE_PYTHON, encoding="utf-8")
    (tmp_path / "app.js").write_text(SAMPLE_JS, encoding="utf-8")

    excluded_dir = tmp_path / "node_modules"
    excluded_dir.mkdir()
    (excluded_dir / "lib.js").write_text("function unused() {}", encoding="utf-8")

    (tmp_path / "broken.py").write_text(SAMPLE_BROKEN_PYTHON, encoding="utf-8")
    (tmp_path / "README.md").write_text("# not a supported language", encoding="utf-8")

    return tmp_path
