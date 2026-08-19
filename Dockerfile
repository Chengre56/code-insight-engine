# syntax=docker/dockerfile:1

FROM python:3.12-slim AS base

# Prevents Python from writing .pyc files and buffering stdout/stderr,
# which keeps container logs flowing in real time.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install runtime dependencies first for better layer caching:
# this layer only rebuilds when pyproject.toml/lockfile changes,
# not on every source edit.
COPY pyproject.toml requirements-lock.txt ./
COPY src/ src/
RUN pip install --no-cache-dir .

# Non-root user for defense-in-depth.
RUN useradd --create-home --shell /bin/bash appuser
USER appuser

WORKDIR /workspace
ENTRYPOINT ["code-insight"]
CMD ["--help"]
