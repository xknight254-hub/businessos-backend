# Module Convention (Phase 3 — M3.1 / M3.3)

Every business domain lives in `app/modules/<domain>/` as a self-contained
package. Each package MUST contain:

| File | Responsibility |
|------|----------------|
| `router.py` | HTTP layer only. Depends on services/repositories; no raw DB/session use. |
| `service.py` | Business logic / orchestration. |
| `repository.py` | **Only** place that touches the DB (SQLAlchemy session). |
| `schemas.py` | Pydantic request/response models for the domain. |
| `models.py` | Re-exports the SQLAlchemy models owned by this domain (`from app.models import ...`). |
| `permissions.py` | Domain slice of the global `PERMISSIONS` map. |
| `tasks.py` | Async/background jobs (Celery/RQ when Phase 6 lands). |
| `events.py` | Domain event names for the Phase 4 event bus. |
| `tests/` | Module-scoped tests. |

## Canvas modules (12)

| Module | Domain | Source of router |
|--------|--------|----------------|
| `auth` | Authentication & users | `app.api.auth.routes` (re-exported) |
| `inventory` | Products & stock | `router.py` (canonical) |
| `crm` | Customers & credit | `router.py` (canonical) |
| `sales` | Sales & transactions | `router.py` (canonical) |
| `accounting` | Payments & M-Pesa | `router.py` (canonical) |
| `procurement` | Suppliers | skeleton |
| `payroll` | Staff pay | skeleton |
| `hr` | Staff admin | skeleton |
| `analytics` | Reporting | skeleton |
| `ai` | AI / memory / DNA | `app.api.ai.routes` (re-exported) |
| `automation` | Rules engine | `app.api.automation.routes` (re-exported) |
| `notifications` | Alerts | skeleton |

## Backward-compat shims

`app/schemas/<d>.py` and `app/repositories/<d>.py` are thin
re-export shims pointing into `app/modules/<d>/`. They exist so tests and
older imports keep resolving; new code should import from
`app.modules.<d>.<layer>` directly.

## Rules

- Routers NEVER import `sqlalchemy` session primitives for queries. They call
  `app.modules.<d>.repository.<X>Repository`.
- Services depend on repositories, not on the raw session.
- Adding a feature = adding to the relevant module package, not a new flat file
  under `app/api/` or `app/services/`.
