# syntax=docker/dockerfile:1

# ── Builder ──────────────────────────────────────────────────────────────────
# Resolve and install the locked dependency set into a self-contained venv.
FROM python:3.12-slim AS builder

# uv: fast, lockfile-driven installer. Pinned copy from the official image.
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv

# build-essential is needed to compile celery[librabbitmq]'s C extension.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

# Install deps first (cached layer) using only the lockfile + project metadata.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# ── Runtime ──────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# librabbitmq links against librt/libssl at runtime; slim already has them, but
# install ca-certificates for outbound TLS (OpenAI, Expo, RevenueCat, S3).
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Bring in the resolved virtualenv from the builder.
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Application code + migrations (run as a one-shot `migrate` service).
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./alembic.ini

# Drop root. Pre-create the celery beat schedule dir owned by appuser so the
# named volume mounted there inherits writable ownership on first use.
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /var/lib/celery \
    && chown -R appuser:appuser /app /var/lib/celery
USER appuser

EXPOSE 8000

# Default command: API server. Worker/beat/migrate override this in compose.
CMD ["gunicorn", "app.main:app", \
     "-k", "uvicorn.workers.UvicornWorker", \
     "-w", "4", "-b", "0.0.0.0:8000"]
