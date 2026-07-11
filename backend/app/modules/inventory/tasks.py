"""Inventory module tasks (async/background jobs).

Skeleton per M3.1 convention. Wire to Celery/RQ when Phase 6 lands.
"""
from __future__ import annotations


async def low_stock_alert(business_id: str) -> None:
    """Notify owner when stock falls below threshold. (stub)"""
    return None
