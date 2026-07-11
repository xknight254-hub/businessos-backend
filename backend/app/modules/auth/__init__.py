"""Auth module (M3.1/M3.3).

Re-exports the existing auth router (its code lives in app.api.auth.routes
until a deeper fold is warranted). Module package satisfies the convention.
"""
from app.api.auth.routes import router

__all__ = ["router"]
