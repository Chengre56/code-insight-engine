"""
Multi-language code parser.

Computes per-file metrics:

* Line counts (total / code / comment / blank)
* Comment density
* Function and class counts
* Cyclomatic complexity (whole-file, plus a per-function breakdown for
  Python where a true AST is available)

Python files are analyzed with the standard library ``ast`` module for
exact results. All other registered languages (JavaScript, TypeScript,
Java, Go, Rust, etc.) fall back to a lexical/regex-based analyzer that
is intentionally conservative -- it will not achieve AST-level
precision, but it is dependency-free and good enough for comparative
quality metrics across a codebase.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

from code_insight.core.config import LanguageSpec, detect_language
from code_insight.utils.exceptions import FileReadError, UnsupportedLanguageError
from code_insight.utils.logger import get_logger

logger = get_logger(__name__)

# Base complexity of any function/file (a single linear path through it).
_BASE_COMPLEXITY = 1


@dataclass
class FunctionComplexity:
    """Cyclomatic complexity of a single function/method.

    Attributes:
        name: Function or method name.
        complexity: McCabe cyclomatic complexity score.
        line_number: 1-indexed line where the function is defined.
    """

    name: str
    complexity: int
    line_number: int


@dataclass
class FileMetrics:
    """All computed metrics for a single source file.

    Attributes:
        file_path: Path to the analyzed file.
        language: Detected language name (e.g. ``"Python"``).
        total_lines: Total number of lines in the file.
        code_lines: Lines containing executable/structural code.
        comment_lines: Lines that are wholly or partially comments.
        blank_lines: Lines containing only whitespace.
        comment_density: ``comment_lines / total_lines`` (0.0 if empty).
        function_count: Number of function/method definitions found.
        class_count: Number of class definitions found.
        cyclomatic_complexity: Total McCabe complexity summed across the file.
        function_complexities: Per-function complexity breakdown (Python only;
            empty for lexically-analyzed languages).
        error: Populated if the file could not be parsed; when set, all
            numeric fields default to zero and should not be trusted.
    """

    file_path: Path
    language: str
    total_lines: int = 0
    code_lines: int = 0
    comment_lines: int = 0
    blank_lines: int = 0
    comment_density: float = 0.0
    function_count: int = 0
    class_count: int = 0
    cyclomatic_complexity: int = 0
    function_complexities: list[FunctionComplexity] = field(default_factory=list)
    error: str | None = None

    @property
    def max_function_complexity(self) -> int:
        """Highest single-function complexity in this file (0 if none)."""
        if not self.function_complexities:
            return 0
        return max(fc.complexity for fc in self.function_complexities)

    def to_dict(self) -> dict[str, object]:
        """Serialize to a JSON-friendly dictionary."""
        return {
            "file_path": str(self.file_path),
            "language": self.language,
            "total_lines": self.total_lines,
            "code_lines": self.code_lines,
            "comment_lines": self.comment_lines,
            "blank_lines": self.blank_lines,
            "comment_density": round(self.comment_density, 4),
            "function_count": self.function_count,
            "class_count": self.class_count,
            "cyclomatic_complexity": self.cyclomatic_complexity,
            "max_function_complexity": self.max_function_complexity,
            "functions": [
                {"name": fc.name, "complexity": fc.complexity, "line": fc.line_number}
                for fc in self.function_complexities
            ],
            "error": self.error,
        }


# Decision-point node types that each add +1 to McCabe complexity for Python.
_PY_COMPLEXITY_NODES: tuple[type[ast.AST], ...] = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.Try,
    ast.With,
    ast.AsyncWith,
    ast.Assert,
    ast.comprehension,
)


class CodeParser:
    """Parses individual source files into :class:`FileMetrics`.

    Instances are stateless aside from configuration read at construction
    time, so a single parser can be reused (and is thread-safe for reads)
    across an entire analysis run.
    """

    def __init__(self, encoding: str = "utf-8") -> None:
        """Initialize the parser.

        Args:
            encoding: Text encoding used to read source files. Falls back
                to a Latin-1 decode (which never raises) if this fails.
        """
        self._encoding = encoding

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def parse_file(self, path: Path) -> FileMetrics:
        """Analyze a single file and return its computed metrics.

        This method never raises for expected failure modes (unreadable
        file, unsupported extension, syntax errors); instead it returns a
        :class:`FileMetrics` with the ``error`` field populated, so a
        batch analysis run can continue past individual bad files.

        Args:
            path: Path to the source file.

        Returns:
            Computed (or error-annotated) :class:`FileMetrics`.
        """
        spec = detect_language(path)
        if spec is None:
            err = UnsupportedLanguageError(path, path.suffix)
            logger.warning(str(err))
            return FileMetrics(file_path=path, language="unknown", error=str(err))

        try:
            source = self._read_source(path)
        except FileReadError as exc:
            logger.warning(str(exc))
            return FileMetrics(file_path=path, language=spec.name, error=str(exc))

        metrics = FileMetrics(file_path=path, language=spec.name)
        self._compute_line_metrics(source, spec, metrics)

        if spec.name == "Python":
            self._analyze_python(source, path, metrics)
        else:
            self._analyze_generic(source, metrics)

        return metrics

    # ------------------------------------------------------------------ #
    # File I/O
    # ------------------------------------------------------------------ #

    def _read_source(self, path: Path) -> str:
        """Read a file's text content, raising :class:`FileReadError` on failure."""
        try:
            return path.read_text(encoding=self._encoding)
        except UnicodeDecodeError:
            try:
                return path.read_text(encoding="latin-1")
            except OSError as exc:
                raise FileReadError(path, exc) from exc
        except OSError as exc:
            raise FileReadError(path, exc) from exc

    # ------------------------------------------------------------------ #
    # Line-level metrics (language-agnostic, comment-syntax aware)
    # ------------------------------------------------------------------ #

    def _compute_line_metrics(self, source: str, spec: LanguageSpec, metrics: FileMetrics) -> None:
        lines = source.splitlines()
        metrics.total_lines = len(lines)

        blank = 0
        comment = 0
        in_block_comment = False

        for raw_line in lines:
            line = raw_line.strip()

            if not line:
                blank += 1
                continue

            if in_block_comment:
                comment += 1
                if spec.block_comment_end and spec.block_comment_end in line:
                    in_block_comment = False
                continue

            if spec.block_comment_start and spec.block_comment_start in line:
                comment += 1
                # Block comment opened and closed on the same line.
                after_open = line.split(spec.block_comment_start, 1)[1]
                if spec.block_comment_end and spec.block_comment_end in after_open:
                    continue
                in_block_comment = True
                continue

            if any(line.startswith(token) for token in spec.line_comment):
                comment += 1
                continue

            # Not blank, not a comment -> counts as code.
            # (Trailing inline comments are intentionally still "code" lines.)

        metrics.blank_lines = blank
        metrics.comment_lines = comment
        metrics.code_lines = metrics.total_lines - blank - comment
        metrics.comment_density = (
            metrics.comment_lines / metrics.total_lines if metrics.total_lines else 0.0
        )

    # ------------------------------------------------------------------ #
    # Python: exact AST-based analysis
    # ------------------------------------------------------------------ #

    def _analyze_python(self, source: str, path: Path, metrics: FileMetrics) -> None:
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError as exc:
            metrics.error = f"SyntaxError: {exc.msg} (line {exc.lineno})"
            logger.warning("Failed to parse %s: %s", path, metrics.error)
            return

        function_types = (ast.FunctionDef, ast.AsyncFunctionDef)
        functions = [n for n in ast.walk(tree) if isinstance(n, function_types)]
        classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]

        metrics.function_count = len(functions)
        metrics.class_count = len(classes)

        total_complexity = 0
        for func in functions:
            complexity = self._python_function_complexity(func)
            total_complexity += complexity
            metrics.function_complexities.append(
                FunctionComplexity(name=func.name, complexity=complexity, line_number=func.lineno)
            )

        # Module-level branching (outside any function) still contributes
        # to the file's overall complexity even though it has no "function".
        module_level_decision_points = sum(
            1
            for node in ast.iter_child_nodes(tree)
            if isinstance(node, _PY_COMPLEXITY_NODES)
        )

        metrics.cyclomatic_complexity = (
            total_complexity if functions else _BASE_COMPLEXITY + module_level_decision_points
        )
        if functions:
            metrics.cyclomatic_complexity += module_level_decision_points

        metrics.function_complexities.sort(key=lambda fc: fc.complexity, reverse=True)

    @staticmethod
    def _python_function_complexity(func_node: ast.AST) -> int:
        """Compute McCabe cyclomatic complexity for a single function body.

        Complexity starts at 1 (one linear path) and is incremented once
        per decision point: ``if``/``elif``, loops, ``except`` clauses,
        boolean operators (each extra operand), comprehension ``for``
        clauses, ``with`` statements, ``assert``, and ternary expressions.
        """
        complexity = _BASE_COMPLEXITY
        for node in ast.walk(func_node):
            if isinstance(node, _PY_COMPLEXITY_NODES):
                complexity += 1
            elif isinstance(node, ast.ExceptHandler):
                complexity += 1
            elif isinstance(node, ast.BoolOp):
                # `a and b and c` has 2 decision points, not 1.
                complexity += max(len(node.values) - 1, 1)
            elif isinstance(node, ast.IfExp):
                complexity += 1
            elif isinstance(node, ast.Match):
                complexity += max(len(node.cases) - 1, 0)
        return complexity

    # ------------------------------------------------------------------ #
    # Generic (non-Python): lexical/regex-based analysis
    # ------------------------------------------------------------------ #

    # Matches common function-defining constructs across C-family and
    # scripting languages: `function foo(`, `foo() {`, `const foo = (…) =>`,
    # `def foo(`, `fn foo(`, `func foo(`, class methods, etc.
    _FUNC_PATTERN = re.compile(
        r"""
        \b(?:function|def|fn|func)\s+\w+\s*\(          # function/def/fn/func name(
        |
        \b\w+\s*=\s*(?:async\s+)?\([^)]*\)\s*=>       # const name = (...) =>
        |
        \b(?:public|private|protected|static|\s)*\w+\s+\w+\s*\([^)]*\)\s*\{  # Java/C# style method
        """,
        re.VERBOSE,
    )

    _CLASS_PATTERN = re.compile(r"\b(?:class|struct|interface)\s+\w+")

    # Decision-point tokens for a heuristic (non-AST) complexity estimate.
    _COMPLEXITY_TOKENS = re.compile(
        r"\b(if|else if|elif|for|foreach|while|case|catch|except)\b|(\&\&|\|\|)"
    )

    def _analyze_generic(self, source: str, metrics: FileMetrics) -> None:
        metrics.function_count = len(self._FUNC_PATTERN.findall(source))
        metrics.class_count = len(self._CLASS_PATTERN.findall(source))

        decision_points = len(self._COMPLEXITY_TOKENS.findall(source))
        metrics.cyclomatic_complexity = _BASE_COMPLEXITY + decision_points
        # Per-function breakdown is not available without a real parser
        # for these languages; `function_complexities` stays empty and
        # callers should treat `cyclomatic_complexity` as file-level only.
