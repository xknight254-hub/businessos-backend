"""Auth module router (M3.1/M3.3).

Re-exports the existing auth router (code in app.api.auth.routes).
Satisfies the module convention; deeper fold pending.
"""
from app.api.auth.routes import router

__all__ = ["router"]
