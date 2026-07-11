"""Business insights (Phase 5 — M5.4).

Gathers structured signals from the ObservationEngine and asks the
model gateway (via the router) to turn them into plain-language,
actionable insights. If there isn't enough data, returns the engine's
own guidance instead of calling the model.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.observation import ObservationEngine
from app.services.llm import chat, GatewayError
from app.services.model_router import model_router


class InsightService:
    def __init__(self, db: AsyncSession, business_id: str) -> None:
        self.db = db
        self.business_id = business_id
        self.engine = ObservationEngine(db, business_id)

    async def _signals(self) -> dict:
        enough = await self.engine.has_enough_data
        if not enough:
            days = await self.engine._days_of_data()
            txs = await self.engine._total_transactions()
            return {
                "ready": False,
                "days_of_data": days,
                "total_transactions": txs,
                "min_days_needed": self.engine.min_data_days,
                "min_transactions_needed": self.engine.min_tx_per_sku,
            }
        return {
            "ready": True,
            "peak_hours": await self.engine.detect_peak_hours(),
            "fast_movers": await self.engine.detect_fast_movers(),
            "anomalies": await self.engine.detect_anomalies(),
            "insights": await self.engine.get_insights(limit=5),
        }

    async def generate(self, *, system: str | None = None) -> dict:
        sig = await self._signals()
        if not sig.get("ready"):
            return {
                "ready": False,
                "insights": (
                    f"Not enough data yet. Have {sig.get('days_of_data')} days "
                    f"and {sig.get('total_transactions')} transactions; need "
                    f"{sig.get('min_days_needed')} days and "
                    f"{sig.get('min_transactions_needed')} transactions before "
                    "AI insights activate."
                ),
            }
        spec = model_router.resolve("insight")
        prompt = (
            "You are a Kenyan SME business analyst. Given these signals, "
            "write 3 short, actionable insights a small-business owner can act on today.\n\n"
            f"Signals:\n{sig}"
        )
        try:
            text = await chat(prompt, system=system, model=spec.name, temperature=0.4)
        except GatewayError as e:
            return {"ready": True, "model_error": str(e), "signals": sig}
        return {"ready": True, "narrative": text, "model": spec.name}


# compatibility alias used by router import
InsightGenerator = InsightService
