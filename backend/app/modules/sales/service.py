"""sales module service layer (M3.1/M3.3).

Business orchestration lives here; depends on the module repository,
never on the raw session. Currently thin — routers call the repository
directly for CRUD; richer use-cases will be added here.
"""
from __future__ import annotations
