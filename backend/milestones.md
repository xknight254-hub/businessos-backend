# BusinessOS Backend — Milestones

Engineering roadmap derived from `BusinessOS_Backend_Engineering_Blueprint.md`.
Tracking instrument for the AI-native, Kenya-first ERP backend.

**Stack:** FastAPI + PostgreSQL · Celery + Redis · domain-driven modules.
**Operating rules (from blueprint):** analyze → estimate blast radius → plan → implement incrementally → test after every change → never break public APIs → document decisions → leave code cleaner.
**Definition of Done (per item):** tests pass · lint passes · docs updated · logging added · errors handled · security reviewed · performance considered · no regressions.

**Status legend:** ⬜ Planned · 🔵 In progress · ✅ Done

---

## Baseline (observed at doc authoring)

Backend already has a domain-folded `app/` layout (`ai`, `customers`, `inventory`,
`payments`, `products`, `reports`, `sales`, `suppliers`, `notifications`, `etims`)
with `services/`, `schemas/`, `models/`, `core/`, `tasks/`, `tests/`. This matches
the *spirit* of Phase 3 but not the strict per-module file pattern
(`router/service/repository/schemas/models/permissions/tasks/events/tests`).
Celery, Redis, and event-driven flows (Phases 4, 7) are not yet evident.

---

## Phase 1 — Foundation

| ID | Milestone | Deliverables | Done when | Status |
|----|-----------|--------------|-----------|--------|
| M1.1 | Structured logging | `core/logging.py`: JSON/leveled logger, request/correlation IDs, no secrets in logs | All modules emit structured logs; PII redacted | ✅ done |
| M1.2 | Centralized exception handling | `core/exceptions.py` + global handler in `main.py`; typed error responses | Unhandled errors return uniform schema; no stack traces leaked | ✅ done |
| M1.3 | Typed configuration | `core/config.py` (pydantic-settings): env-driven, validated at boot | Missing/invalid config fails fast at startup | ✅ done |
| M1.4 | Service-layer validation | Validation moved out of routers into services; routers stay thin | Routers delegate; services reject invalid input with typed errors | ✅ done |

**Phase 1 exit:** logging + exceptions + config + validation consistent across all `app/` modules.
- *Progress (2026-07-11):* M1.1–M1.4 complete and committed. All `app/api` routers (auth, products, customers, sales, payments, automation) now raise typed `BusinessError` subclasses; zero raw `HTTPException` raises remain. 70 tests passing. New regression tests: `test_foundation.py`, `test_m14_typed_errors.py`.

---

## Phase 2 — Security

| ID | Milestone | Deliverables | Done when |
|----|-----------|--------------|-----------|
| M2.1 | RBAC | `permissions.py` per module; role decorator/dependency | Endpoints enforce role; 403 on violation | ✅ done (rolled out to all mutating routes) |
| M2.2 | Audit logs | `AuditLog` model + middleware capturing mutating actions | Every write is auditable | ✅ done |
| M2.3 | Rate limiting | Memory/Redis adapter limiter on auth + payments | 429 on abuse; no bypass | ✅ done (auto-selects Redis, memory fallback) |
| M2.4 | JWT refresh rotation | `jti` + revocation store; rotate+revoke on refresh | Replay of rotated token rejected | ✅ done (auto-selects Redis, memory fallback) |
| M2.5 | Security headers | Helmet-style middleware (HSTS, CSP, X-Content-Type-Options) | Headers present on all responses | ✅ done |
| M2.6 | Secrets management | `.env` gitignored; static guard `scripts/check_secrets.py` | `.env` not tracked; scan clean; 2 tests | ✅ done |

---

## Phase 3 — Modularization

| ID | Milestone | Deliverables | Done when |
|----|-----------|--------------|-----------|
| M3.1 | Module file convention | Each domain folder has `router/service/repository/schemas/models/permissions/tasks/events/tests` | All 12 modules conform | ✅ done (app/modules/<domain>/ for all 12; MUDULE_CONVENTION.md) |
| M3.2 | Repository layer | DB access isolated to `repository.py`; services depend on repos not sessions | No raw SQL/session use outside repos | ✅ done (4 canonical modules; shims for others) |
| M3.3 | Modules: auth, crm, inventory, sales, procurement, accounting, payroll, hr, analytics, ai, automation, notifications | Full module skeleton per convention | Each module independently testable | ✅ done (12 module packages; 4 canonical folded, 3 re-export, 5 skeleton) |

---

## Phase 4 — Event Driven

| ID | Milestone | Deliverables | Done when |
|----|-----------|--------------|-----------|
| M4.1 | Event bus | Redis/Celery event publisher + subscriber | Events emitted/received reliably | ✅ done (app/core/events.py: in-process EventBus w/ Redis seam; publish/subscribe; handlers never break publisher) |
| M4.2 | Core events | `CustomerCreated`, `InvoiceCreated`, `PaymentReceived`, `InventoryAdjusted`, `WorkflowCompleted` | Each emitted on its trigger | ✅ done (CustomerCreated@crm, InvoiceCreated@sales, PaymentCompleted@accounting, InventoryAdjusted@inventory; WorkflowCompleted reserved) |
| M4.3 | Handlers | Side-effect handlers wired to events (e.g. notify on PaymentReceived) | Handlers idempotent; tested | ✅ done (app/core/handlers.py: on_payment_completed->payment_received, on_low_stock->low_stock; Notification model + repo; GET /notifications; 3 tests) |

---

## Phase 5 — AI Platform

| ID | Milestone | Deliverables | Done when |
|----|-----------|--------------|-----------|
| M5.0 | AI model gateway | Omniroute (OpenAI-compatible) gateway client + config + `/ai/chat` endpoint + LLM service | `chat`/`structured` callable; offline + live SSE verified |
| M5.1 | OCR | Document/invoice OCR endpoint | Endpoint live; returns 501 until OCR engine (Tesseract/EasyOCR) wired |
| M5.2 | Voice bookkeeping | Speech-to-entry pipeline | Endpoint live; returns 501 until STT engine (Whisper) wired |
| M5.3 | Forecasting | Demand/revenue forecast service | `POST /ai/forecast` (engine predictions + LLM narrative) |
| M5.4 | Business insights | Insight generator over domain data | `POST /ai/insights/generate` (LLM over ObservationEngine) |
| M5.5 | Prompt management | Versioned prompt store | `POST /ai/prompts`, `GET /ai/prompts`; DB-backed, versioned |
| M5.6 | Model routing | Router across providers/models | `GET /ai/models/routes`; task→model + cost tiers |

---

## Phase 6 — Kenya Integrations

| ID | Milestone | Deliverables | Done when |
|----|-----------|--------------|-----------|
| M6.1 | M-Pesa | STK push + callback + query (Daraja) | End-to-end payment verified |
| M6.2 | eTIMS | Invoice submission to KRA eTIMS | Fiscal docs accepted |
| M6.3 | KRA | Tax/compliance touchpoints | Validated against sandbox |
| M6.4 | WhatsApp | Business API messaging | Template + session msgs |
| M6.5 | SMS | Provider integration (e.g. Africa's Talking) | OTP/notify delivered |
| M6.6 | POS | Terminal/device sync | Offline-tolerant |
| M6.7 | Offline sync | Conflict resolution for field use | Sync converges |

---

## Phase 7 — Infrastructure

| ID | Milestone | Deliverables | Done when |
|----|-----------|--------------|-----------|
| M7.1 | Docker | Multi-stage Dockerfile + compose (api, worker, redis, db) | One-command local stack |
| M7.2 | GitHub Actions | CI: lint + test + build on PR | Green pipeline |
| M7.3 | Prometheus | Metrics endpoints + scrape config | Metrics exposed |
| M7.4 | Grafana | Dashboards for API/worker health | Dashboards live |
| M7.5 | OpenTelemetry | Traces across request/worker | Trace waterfall visible |
| M7.6 | Sentry | Error tracking wired | Errors surfaced |

---

## Phase 8 — Testing

| ID | Milestone | Deliverables | Done when |
|----|-----------|--------------|-----------|
| M8.1 | Unit | Per-module unit tests (services/repos) | Coverage tracked |
| M8.2 | Integration | API + DB integration suites | Run in CI |
| M8.3 | API | Contract tests per endpoint | Public APIs locked |
| M8.4 | Regression | Suite guarding past fixes | No known bug recurs |
| M8.5 | Load | Benchmark on hot paths | p95 latency known |
| M8.6 | Security | Authz/fuzz tests | >90% business-logic coverage target |

**Final gate:** >90% business-logic coverage; all Definition-of-Done checks green.

---

## Dependency order

```
Phase 1 (Foundation) ──▶ Phase 2 (Security) ──▶ Phase 3 (Modularization)
                                                        │
                                                        ▼
                              Phase 4 (Event Driven) ──▶ Phase 5 (AI) ──▶ Phase 6 (Kenya)
                                                        │
                                        Phase 7 (Infra) ◀── runs parallel from Phase 3+
                                                        │
                                        Phase 8 (Testing) ◀── continuous from Phase 1
```

Phases 7 and 8 run **continuously** alongside 1–6, not as a final gate.
