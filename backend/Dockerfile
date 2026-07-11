# syntax=docker/dockerfile:1

# ---- builder ----
FROM python:3.11-slim AS builder
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
COPY requirements.txt .
RUN pip install --upgrade pip && pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt


# ---- runtime ----
FROM python:3.11-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    APP_HOME=/app

# runtime deps for psycopg2-binary / cryptography / bcrypt + tesseract OCR
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl ca-certificates tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# copy prebuilt wheels + install
COPY --from=builder /wheels /wheels
COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --no-cache-dir --find-links=/wheels -r requirements.txt \
    && rm -rf /wheels

# app source
COPY app ./app
COPY alembic.ini ./alembic.ini
COPY migrations ./migrations
COPY pyproject.toml .

# non-root
RUN useradd -m -u 10001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Run migrations then start. init_db() creates all tables idempotently.
CMD ["sh", "-c", "python -m app.core.migrate || true; uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1"]
