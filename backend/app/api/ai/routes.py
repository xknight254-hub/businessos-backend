from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.api.auth.dependencies import get_current_user
from app.models import User
from app.services.observation import ObservationEngine

router = APIRouter(prefix="/ai", tags=["AI/Observation"])


@router.get("/observations")
async def get_observations(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    engine = ObservationEngine(db, user.business_id)
    insights = await engine.get_insights(limit)
    return {"items": insights, "total": len(insights)}


@router.get("/observations/peak-hours")
async def peak_hours(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    engine = ObservationEngine(db, user.business_id)
    return await engine.detect_peak_hours()


@router.get("/observations/fast-movers")
async def fast_movers(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    engine = ObservationEngine(db, user.business_id)
    items = await engine.detect_fast_movers()
    return {"items": items, "total": len(items)}


@router.get("/observations/anomalies")
async def anomalies(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    engine = ObservationEngine(db, user.business_id)
    items = await engine.detect_anomalies()
    return {"items": items, "total": len(items)}


@router.get("/observations/ready")
async def check_readiness(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    engine = ObservationEngine(db, user.business_id)
    days = await engine._days_of_data()
    txs = await engine._total_transactions()
    prophet = await engine.get_peak_hours_predictions()
    return {
        "days_of_data": days,
        "min_days_needed": engine.min_data_days,
        "total_transactions": txs,
        "min_transactions_needed": engine.min_tx_per_sku,
        "ready": await engine.has_enough_data,
        "prophet_status": prophet,
    }
