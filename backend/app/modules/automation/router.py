"""Automation module router (M3.1/M3.3).

Re-exports the existing automation router (code in app.api.automation.routes).
Satisfies the module convention; deeper fold pending.
"""
from app.api.automation.routes import router

__all__ = ["router"]
