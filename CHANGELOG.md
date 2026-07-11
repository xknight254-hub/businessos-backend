# Changelog

All notable changes to BusinessOS backend are documented here.

## [Unreleased]

### Phase 5 — AI Platform
- **M5.0** Omniroute AI gateway (OpenAI-compatible, SSE streaming). `POST /ai/chat`.
- **M5.1 / M5.2** OCR / Voice interface endpoints (`/ai/ocr`, `/ai/voice/transcribe`) — engine-gated (501 until a real engine is wired).
- **M5.3** Forecasting endpoint (`/ai/forecast`) over ObservationEngine + LLM narrative.
- **M5.4** Business insights (`/ai/insights/generate`).
- **M5.5** Versioned prompt management (`/ai/prompts`) + `prompts` table.
- **M5.6** Model routing (`/ai/models/routes`) — task→model + cost tiers.

### Phase 4 — Event-Driven
- **M4.1 / M4.2 / M4.3** Domain events + side-effect handlers (payment→notification, low_stock→notification). `GET /notifications`.

### Phase 3 — Modularization
- 12 domain module packages (canonical 8-file layout). `repositories/*` + `schemas/*` backward-compat shims.

### Phase 7 — Production Hardening
- `Dockerfile` (multi-stage, non-root, runs migrate→uvicorn).
- `docker-compose.yml` (postgres:16 + redis:7 + backend, healthchecked).
- Alembic: `migrations/env.py` + initial migration `2ac145176d01` (19 tables, applied vs real Postgres).
- CI workflow (`.github/workflows/ci.yml`): test + build.
- `requirements.txt` pin corrections + missing deps (numpy, scikit-learn, openai, langchain, jinja2, aiosqlite, bcrypt pin).

### Phase 1 → 2 — Foundation & Security
- FastAPI app, SQLite (dev) / Postgres (prod) via `DATABASE_URL`.
- Phone+pin auth (JWT), RBAC, M-Pesa (mock mode), core modules.

## [2026-07-11] Postgres Cutover (live)
- Switched the running preview service from systemd+SQLite to Docker Compose on Postgres 16 + Redis 7.
- Fixed naive/aware datetime bug that only manifested on Postgres.
- Fixed `passlib`/`bcrypt>=4.1` incompatibility (pinned `bcrypt==4.0.1`).
- Verified: register/login round-trip writes+reads Postgres; `/health` 200; suite 107 passed.
- SQLite backup retained at `backend/businessos_preview.db.bak-20260711-175306` (untracked, local only).
