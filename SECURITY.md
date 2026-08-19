# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.x     | ✅ |

## Scope & Threat Model

`code-insight-engine` is a **local, read-only static analysis CLI**. It:

- Reads source files from the filesystem paths you point it at.
- Never executes, imports, or evaluates the code it analyzes (Python files are
  parsed with `ast.parse`, never `exec`/`eval`/`import`).
- Makes no network calls.
- Writes output only to stdout or an explicitly-provided `--output` file path.

The realistic attack surface is therefore narrow: malformed/adversarial input
files causing a crash, excessive resource use, or (in principle) a path
traversal via crafted `--output` arguments. All user-supplied configuration
(`complexity_threshold`, `exclude_patterns`, target paths) is validated at
construction time in `AnalysisConfig` before any file I/O occurs.

## Reporting a Vulnerability

If you find a security issue (e.g. a crafted file that causes unbounded
resource consumption, or a path handling bug), please **open a private
security advisory** on this repository (GitHub → Security → Advisories →
"Report a vulnerability") rather than a public issue, so a fix can ship
before details are public.

Please include:

- A minimal reproduction (sample file/command).
- The version of `code-insight-engine` and Python you're using.
- The observed vs. expected behavior.

## Dependency Auditing

Runtime dependencies are intentionally minimal (`click` only). CI runs
`pip-audit` against the dependency tree on every push and pull request to
catch known vulnerabilities in `click` or transitive dependencies early.
