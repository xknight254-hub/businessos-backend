"""Demand / revenue forecasting (Phase 5 — M5.3).

Wraps the ObservationEngine's statistical predictions and adds an
LLM narrative on top. The statistical layer is the source of truth;
the model only explains it in business language.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.observation import ObservationEngine
from app.services.llm import chat, GatewayError
from app.services.model_router import model_router


class ForecastService:
    def __init__(self, db: AsyncSession, business_id: str) -> None:
        self.db = db
        self.business_id = business_id
        self.engine = ObservationEngine(db, business_id)

    async def forecast(self, *, system: str | None = None) -> dict:
        enough = await self.engine.has_enough_data
        peak = await self.engine.get_peak_hours_predictions()
        if not enough:
            return {
                "ready": False,
                "peak_hours_prediction": peak,
                "narrative": "Need more sales history before forecasting activates.",
            }
        spec = model_router.resolve("forecast_narrative")
        prompt = (
            "You are a Kenyan SME demand planner. Summarise this forecast in "
            "2 bullet points a shop owner can use for staffing and stock.\n\n"
            f"Forecast:\n{peak}"
        )
        try:
            narrative = await chat(prompt, system=system, model=spec.name, temperature=0.3)
        except GatewayError as e:
            narrative = f"[model unavailable] {e}"
        return {
            "ready": True,
            "peak_hours_prediction": peak,
            "narrative": narrative,
            "model": spec.name,
        }
