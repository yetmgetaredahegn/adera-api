# M12 / 09 §2 — Production Dockerfile for ADERA backend services
# One image used for all three Python roles (api | worker | beat).

FROM python:3.12-slim AS base

# Install system dependencies & Tesseract OCR with Amharic + English language packs (FR-3.2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-amh \
    tesseract-ocr-eng \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv binary from Astral ghcr image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Cache dependencies layer
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy application source code & prompts
COPY app/ app/
COPY prompts/ prompts/
COPY evals/ evals/
COPY alembic/ alembic/
COPY alembic.ini ./

# Non-root unprivileged execution user for security hardening
RUN useradd -m runner && chown -R runner /app
USER runner

# Role picked at runtime via Compose command override (api | worker | beat)
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
