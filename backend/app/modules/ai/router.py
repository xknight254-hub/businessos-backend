"""AI module router (M3.1/M3.3).

Re-exports the existing AI router (its code lives in app.api.ai.routes
until a deeper fold is warranted). Module package satisfies the convention.
"""
from app.api.ai.routes import router

__all__ = ["router"]
