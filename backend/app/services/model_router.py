"""Model routing (Phase 5 — M5.6).

Maps a task type to a model + cost tier so domain code asks for a
*capability* ("summarize", "classify", "vision") rather than a raw
model name. The gateway stays the only thing that knows the host.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class CostTier(str, Enum):
    cheap = "cheap"
    balanced = "balanced"
    premium = "premium"


@dataclass
class ModelSpec:
    name: str
    tier: CostTier
    supports_json: bool = True
    supports_vision: bool = False


# Default routing table. Override per business later if needed.
DEFAULT_ROUTES: dict[str, ModelSpec] = {
    "chat": ModelSpec("gpt-4o-mini", CostTier.cheap),
    "summarize": ModelSpec("gpt-4o-mini", CostTier.cheap),
    "classify": ModelSpec("gpt-4o-mini", CostTier.cheap),
    "insight": ModelSpec("gpt-4o-mini", CostTier.balanced),
    "forecast_narrative": ModelSpec("gpt-4o-mini", CostTier.balanced),
    "extract": ModelSpec("gpt-4o-mini", CostTier.balanced),
    "vision": ModelSpec("gpt-4o-mini", CostTier.balanced, supports_vision=True),
    "reasoning": ModelSpec("gpt-4o-mini", CostTier.premium),
}


class ModelRouter:
    def __init__(self, routes: Optional[dict[str, ModelSpec]] = None) -> None:
        self._routes = dict(DEFAULT_ROUTES)
        if routes:
            self._routes.update(routes)

    def resolve(self, task: str, *, preferred: Optional[str] = None) -> ModelSpec:
        """Return the model spec for a task. An explicit `preferred`
        model overrides routing (used for experiments / user choice)."""
        if preferred:
            tier = self._routes.get(task, ModelSpec("gpt-4o-mini", CostTier.balanced)).tier
            return ModelSpec(preferred, tier)
        return self._routes.get(task, ModelSpec("gpt-4o-mini", CostTier.balanced))

    def supports(self, task: str, capability: str) -> bool:
        spec = self.resolve(task)
        if capability == "json":
            return spec.supports_json
        if capability == "vision":
            return spec.supports_vision
        return False

    def list_routes(self) -> dict[str, dict]:
        return {
            k: {"name": v.name, "tier": v.tier.value,
                "supports_json": v.supports_json, "supports_vision": v.supports_vision}
            for k, v in self._routes.items()
        }


model_router = ModelRouter()
