"""Tests for code_insight.analyzers.parser."""

from __future__ import annotations

from pathlib import Path

from code_insight.analyzers.parser import CodeParser


class TestLineMetrics:
    def test_counts_blank_and_comment_lines(self, tmp_path: Path) -> None:
        content = "# a comment\n\nx = 1\ny = 2\n"
        file_path = tmp_path / "sample.py"
        file_path.write_text(content, encoding="utf-8")

        metrics = CodeParser().parse_file(file_path)

        assert metrics.total_lines == 4
        assert metrics.comment_lines == 1
        assert metrics.blank_lines == 1
        assert metrics.code_lines == 2
        assert metrics.error is None

    def test_comment_density_of_empty_file(self, tmp_path: Path) -> None:
        file_path = tmp_path / "empty.py"
        file_path.write_text("", encoding="utf-8")

        metrics = CodeParser().parse_file(file_path)

        assert metrics.total_lines == 0
        assert metrics.comment_density == 0.0

    def test_block_comment_spanning_multiple_lines_js(self, tmp_path: Path) -> None:
        content = "/*\n * block comment\n */\nfunction f() {}\n"
        file_path = tmp_path / "sample.js"
        file_path.write_text(content, encoding="utf-8")

        metrics = CodeParser().parse_file(file_path)

        assert metrics.comment_lines == 3
        assert metrics.code_lines == 1


class TestPythonAnalysis:
    def test_function_and_class_counts(self, tmp_path: Path) -> None:
        content = (
            "def a():\n    pass\n\n"
            "def b():\n    pass\n\n"
            "class C:\n    def method(self):\n        pass\n"
        )
        file_path = tmp_path / "sample.py"
        file_path.write_text(content, encoding="utf-8")

        metrics = CodeParser().parse_file(file_path)

        assert metrics.function_count == 3  # a, b, method
        assert metrics.class_count == 1

    def test_simple_function_has_complexity_one(self, tmp_path: Path) -> None:
        file_path = tmp_path / "simple.py"
        file_path.write_text("def f(x):\n    return x + 1\n", encoding="utf-8")

        metrics = CodeParser().parse_file(file_path)

        assert len(metrics.function_complexities) == 1
        assert metrics.function_complexities[0].complexity == 1

    def test_branching_increases_complexity(self, tmp_path: Path) -> None:
        content = (
            "def f(x):\n"
            "    if x > 0:\n"
            "        return 1\n"
            "    elif x < 0:\n"
            "        return -1\n"
            "    else:\n"
            "        return 0\n"
        )
        file_path = tmp_path / "branchy.py"
        file_path.write_text(content, encoding="utf-8")

        metrics = CodeParser().parse_file(file_path)

        # base(1) + if(1) + elif(1) = 3
        assert metrics.function_complexities[0].complexity == 3

    def test_loop_and_boolop_increase_complexity(self, tmp_path: Path) -> None:
        content = (
            "def f(items):\n"
            "    total = 0\n"
            "    for item in items:\n"
            "        if item > 0 and item < 100:\n"
            "            total += item\n"
            "    return total\n"
        )
        file_path = tmp_path / "loopy.py"
        file_path.write_text(content, encoding="utf-8")

        metrics = CodeParser().parse_file(file_path)

        # base(1) + for(1) + if(1) + and(1) = 4
        assert metrics.function_complexities[0].complexity == 4

    def test_try_except_increases_complexity(self, tmp_path: Path) -> None:
        content = "def f():\n    try:\n        risky()\n    except ValueError:\n        pass\n"
        file_path = tmp_path / "tryexcept.py"
        file_path.write_text(content, encoding="utf-8")

        metrics = CodeParser().parse_file(file_path)

        # base(1) + try(1) + except(1) = 3
        assert metrics.function_complexities[0].complexity == 3

    def test_syntax_error_is_captured_not_raised(self, tmp_path: Path) -> None:
        file_path = tmp_path / "broken.py"
        file_path.write_text("def broken(:\n    pass\n", encoding="utf-8")

        metrics = CodeParser().parse_file(file_path)

        assert metrics.error is not None
        assert "SyntaxError" in metrics.error

    def test_functions_sorted_by_complexity_descending(self, tmp_path: Path) -> None:
        content = (
            "def simple():\n"
            "    return 1\n\n"
            "def complex_one(x):\n"
            "    if x:\n"
            "        if x > 1:\n"
            "            if x > 2:\n"
            "                return 3\n"
            "    return 0\n"
        )
        file_path = tmp_path / "mixed.py"
        file_path.write_text(content, encoding="utf-8")

        metrics = CodeParser().parse_file(file_path)

        complexities = [fc.complexity for fc in metrics.function_complexities]
        assert complexities == sorted(complexities, reverse=True)
        assert metrics.function_complexities[0].name == "complex_one"


class TestGenericLanguageAnalysis:
    def test_javascript_function_detection(self, tmp_path: Path) -> None:
        content = (
            "function greet(name) {\n"
            "  return `hi ${name}`;\n"
            "}\n\n"
            "const shout = (msg) => msg.toUpperCase();\n"
        )
        file_path = tmp_path / "sample.js"
        file_path.write_text(content, encoding="utf-8")

        metrics = CodeParser().parse_file(file_path)

        assert metrics.function_count >= 2
        assert metrics.error is None

    def test_javascript_class_detection(self, tmp_path: Path) -> None:
        file_path = tmp_path / "sample.js"
        file_path.write_text("class Foo {\n  bar() {}\n}\n", encoding="utf-8")

        metrics = CodeParser().parse_file(file_path)

        assert metrics.class_count == 1

    def test_generic_complexity_estimate_increases_with_branches(self, tmp_path: Path) -> None:
        simple = tmp_path / "simple.js"
        simple.write_text("function f() { return 1; }\n", encoding="utf-8")

        branchy = tmp_path / "branchy.js"
        branchy.write_text(
            "function f(x) {\n"
            "  if (x > 0) { return 1; }\n"
            "  else if (x < 0) { return -1; }\n"
            "  for (let i = 0; i < x; i++) {}\n"
            "  return 0;\n"
            "}\n",
            encoding="utf-8",
        )

        parser = CodeParser()
        simple_metrics = parser.parse_file(simple)
        branchy_metrics = parser.parse_file(branchy)

        assert branchy_metrics.cyclomatic_complexity > simple_metrics.cyclomatic_complexity


class TestUnsupportedAndUnreadableFiles:
    def test_unsupported_extension_sets_error(self, tmp_path: Path) -> None:
        file_path = tmp_path / "data.xyz"
        file_path.write_text("irrelevant", encoding="utf-8")

        metrics = CodeParser().parse_file(file_path)

        assert metrics.error is not None
        assert metrics.language == "unknown"

    def test_nonexistent_file_sets_error(self, tmp_path: Path) -> None:
        missing = tmp_path / "missing.py"

        metrics = CodeParser().parse_file(missing)

        assert metrics.error is not None
