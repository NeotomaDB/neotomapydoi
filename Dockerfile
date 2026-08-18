# --- build stage -------------------------------------------------------------
# psycopg2 is a source build (the project depends on psycopg2, not
# psycopg2-binary), so this stage needs a full toolchain and the libpq headers.
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential \
      libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Installed from PyPI rather than copied from ghcr.io/astral-sh/uv, so the build
# needs no registry beyond the one it already uses. The floor matters: uv must be
# new enough to read uv.lock's `revision` field (currently 3).
RUN pip install --no-cache-dir "uv>=0.11,<0.12"

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# Dependencies first, so the expensive layer is cached across source changes.
COPY pyproject.toml uv.lock README.md LICENSE.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src/ ./src/
RUN uv sync --frozen --no-dev

# --- runtime stage -----------------------------------------------------------
# Only the runtime shared library, not the compiler or headers.
FROM python:3.12-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
      libpq5 \
    && rm -rf /var/lib/apt/lists/*

# WORKDIR is load-bearing twice over: ndbdoi.py opens
# `src/neotomadoi/sql/ds_timeslice.sql` and `neotomadoi.yaml` by CWD-relative
# path, and the copied virtualenv has /app baked into its absolute paths.
WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

COPY src/ ./src/
COPY scripts/ ./scripts/
COPY ndbdoi.py neotomadoi.yaml entrypoint.sh ./
RUN chmod +x entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
