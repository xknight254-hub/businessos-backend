# Progress Report

_Last updated: 2026-07-11_

## Current State

- **Live backend:** Docker Compose stack on **Postgres 16 + Redis 7**, published on `:8000`. systemd `businessos-backend.service` stopped + disabled.
- **Auth:** phone+pin (JWT). Register/login verified writing+reading Postgres.
- **AI gateway:** Omniroute (`http://178.105.198.217:20128/api/v1`), SSE streaming, live-verified.
- **Suite:** 107 passed.
- **Latest commit:** `0015dda` (Postgres cutover fixes).

## Phases Complete

| Phase | Status |
|-------|--------|
| P1 Foundation | ✅ |
| P2 Security | ✅ |
| P3 Modularization | ✅ (reconciled `b73685d`) |
| P4 Event-Driven | ✅ (M4.1–M4.3) |
| P5 AI Platform | ✅ (M5.0–M5.6; M5.1 OCR + M5.2 Voice live via Tesseract/Whisper engines `3189375`/`88432c5`) |
| P7 Hardening | ✅ (Docker, compose, Alembic, CI) |
| P6 Kenya Integrations | 🔄 M6.1✅ M6.4✅ M6.5✅ / M6.2 M6.3 M6.6 M6.7 ⬜ (need creds/hardware) |
| P8 Testing | ✅ 136 passing (latest `3189375`) |

## Open Items

1. **Phase 6 Kenya Integrations** — M6.1/M6.4/M6.5 done (M-Pesa, WhatsApp, SMS). eTIMS/KRA need KRA sandbox creds; POS/offline-sync need hardware/design.
2. **SQLite → Postgres data migration** — the old `businessos_preview.db` was backed up (`backend/businessos_preview.db.bak-20260711-175306`) but its rows were NOT migrated into Postgres (the preview DB had no business data of value; fresh register confirmed working). If legacy rows are needed, a one-off ETL is required.
3. **CI secret handling** — `.github/workflows/ci.yml` uses `SECRET_KEY: ci-secret` and empty Omniroute key (tests run on SQLite, so AI live calls are skipped).

## Verification Notes

- Docker image builds (exit 0); `app.core.migrate` entrypoint runs (exit 0).
- Alembic initial migration applied against real Postgres (19 tables).
- Postgres cutover: register → DB row present; login → JWT; `/health` 200.
- Full suite 136 passed (latest `3189375`).

## Next Recommended Phase

**Remaining Phase 6** needs external input: eTIMS/KRA (KRA sandbox creds), POS (hardware design), offline-sync (conflict strategy). Alternatively **Phase 8 coverage hardening** (raise toward >90% target) or the remaining **CI hardening**. Proceed when directed.
