# Contributing to code-insight-engine

Thanks for considering a contribution. This document covers everything you
need to get set up and submit a change.

## Development setup

```bash
git clone https://github.com/Chengre56/code-insight-engine.git
cd code-insight-engine
pip install -e ".[dev]"
```

## Workflow

1. Fork the repository and create a feature branch:
   ```bash
   git checkout -b feature/my-change
   ```
2. Make your change, with tests. Coverage must stay at or above **85%**
   (enforced via `[tool.coverage.report] fail_under = 85` in `pyproject.toml`).
3. Run the full local quality gate before opening a PR:
   ```bash
   ruff check src tests
   mypy src
   pytest
   ```
4. If you added or changed a runtime/dev dependency, regenerate the lockfiles:
   ```bash
   pip freeze --exclude-editable > requirements-lock.txt        # runtime env
   pip freeze --exclude-editable > requirements-dev-lock.txt     # dev env
   ```
5. Add an entry to `CHANGELOG.md` under an `[Unreleased]` heading.
6. Open a pull request describing the change and its motivation. CI (lint,
   type-check, tests across Python 3.10–3.12, `pip-audit`) must pass.

## Code standards

- **Type hints are mandatory.** `mypy --strict` must pass with no errors.
- **Docstrings** follow Google style (summary line, `Args`/`Returns`/`Raises`)
  on every public module, class, and function.
- **Errors** should raise a specific subclass of `CodeInsightError`
  (`src/code_insight/utils/exceptions.py`), not a bare `Exception`.
- **Fail soft, per file.** Parsing a single bad file should never crash a
  whole analysis run — see how `CodeParser.parse_file` captures errors on
  `FileMetrics.error` instead of raising.
- **Line length** is capped at 100 characters (enforced by `ruff`/`black`).

## Adding support for a new language

Add one entry to `LANGUAGE_REGISTRY` in `src/code_insight/core/config.py`:

```python
".ext": _c_style("LanguageName"),  # for // line + /* block */ comment syntax
# or, for a custom comment syntax:
".ext": LanguageSpec("LanguageName", line_comment=("#",), block_comment_start="...", block_comment_end="..."),
```

File discovery, comment-density calculation, and the generic (non-Python)
complexity heuristic all apply automatically — no other code changes needed
for basic support.

## Reporting bugs / requesting features

Open a GitHub issue with a minimal reproduction (a small sample file plus the
command you ran) and the expected vs. actual output.

## Security issues

Please see [SECURITY.md](SECURITY.md) — do not open a public issue for
security-sensitive reports.
