# syntax=docker/dockerfile:1
#
# Multi-stage build for the AgentLen API and worker.
#
# `builder` resolves and installs dependencies with `uv` into a self-contained
# virtualenv (reproducible: driven by pyproject.toml / uv.lock, not whatever
# happens to be on the host). `runtime` copies only that virtualenv and the
# application code onto a slim base — no compiler, no build cache, no uv
# binary ships in the image that actually runs.

FROM python:3.12-slim AS builder

# build-essential covers the rare dependency without a prebuilt wheel for this
# platform/Python combination; it never leaves this stage.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /build

# Dependencies first, so an application-code change does not invalidate the
# (much slower) dependency-resolution layer. `--frozen` refuses to re-resolve
# — the build fails loudly if pyproject.toml and the committed uv.lock ever
# disagree, instead of silently installing something not actually locked.
# `--no-install-project` installs only what pyproject.toml declares, not the
# package itself — that needs src/, which is not copied in yet.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY alembic ./alembic
COPY alembic.ini ./

# Now installs the project itself (`--no-editable`: runtime code is a copy,
# not a live link back to /build, which stops existing once this stage ends).
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable

# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

RUN groupadd --gid 1000 agentlen \
    && useradd --uid 1000 --gid agentlen --create-home --shell /usr/sbin/nologin agentlen

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --chown=agentlen:agentlen src ./src
COPY --chown=agentlen:agentlen alembic ./alembic
COPY --chown=agentlen:agentlen alembic.ini pyproject.toml ./
COPY --chown=agentlen:agentlen data ./data

# Writable at runtime by the app user: uploaded files land here (LocalFileStorage).
RUN mkdir -p /app/storage && chown agentlen:agentlen /app/storage

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

USER agentlen

EXPOSE 8000

# No ENTRYPOINT: api and worker share this image and select their process via
# `command:` in docker-compose.yml, both running as `agentlen` — nothing here
# re-escalates to root.
CMD ["uvicorn", "agentlen.interfaces.http.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
