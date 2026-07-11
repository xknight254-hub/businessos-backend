"""AI module (M3.1/M3.3).

Re-exports the existing AI router (code in app.api.ai.routes). Satisfies the
module convention; deeper fold pending.
"""
from app.api.ai.routes import router

__all__ = ["router"]
