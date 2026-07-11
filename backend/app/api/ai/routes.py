from fastapi import APIRouter, Depends, Query, UploadFile, File, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.auth.dependencies import get_current_user
from app.models import User
from app.services.observation import ObservationEngine
from app.services.llm import chat, GatewayError
from app.services.model_router import model_router
from app.services.prompt_store import PromptStore
from app.services.insight_service import InsightService
from app.services.forecast_service import ForecastService
from app.services.document_processing import (
    get_document_processor, get_voice_processor,
)

router = APIRouter(prefix="/ai", tags=["AI/Observation"])


# ---------- Existing observation endpoints ----------

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


# ---------- M5.0 raw chat ----------

class ChatRequest(BaseModel):
    prompt: str
    system: str | None = None
    model: str = "gpt-4o-mini"
    temperature: float = 0.3


@router.post("/chat")
async def ai_chat(req: ChatRequest, user: User = Depends(get_current_user)):
    """Call the Omniroute model gateway (Phase 5 M5.0)."""
    try:
        content = await chat(
            req.prompt, system=req.system, model=req.model, temperature=req.temperature
        )
    except GatewayError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    return {"content": content, "model": req.model}


# ---------- M5.6 model routing ----------

@router.get("/models/routes")
async def list_model_routes(user: User = Depends(get_current_user)):
    return {"routes": model_router.list_routes()}


# ---------- M5.5 prompt management ----------

class PromptCreate(BaseModel):
    key: str
    title: str
    template: str
    model: str = "gpt-4o-mini"
    task: str = "insight"


@router.post("/prompts")
async def create_prompt(
    req: PromptCreate, db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    store = PromptStore(db, user.business_id)
    p = await store.create(
        key=req.key, title=req.title, template=req.template,
        model=req.model, task=req.task,
    )
    return {
        "id": p.id, "key": p.key, "version": p.version,
        "title": p.title, "model": p.model, "task": p.task, "is_active": p.is_active,
    }


@router.get("/prompts")
async def list_prompts(
    db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user),
):
    store = PromptStore(db, user.business_id)
    items = await store.list_()
    return {
        "items": [
            {"id": p.id, "key": p.key, "version": p.version, "title": p.title,
             "model": p.model, "task": p.task, "is_active": p.is_active}
            for p in items
        ],
        "total": len(items),
    }


# ---------- M5.4 business insights ----------

@router.post("/insights/generate")
async def generate_insights(
    db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user),
):
    svc = InsightService(db, user.business_id)
    return await svc.generate()


# ---------- M5.3 forecasting ----------

@router.post("/forecast")
async def forecast(
    db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user),
):
    svc = ForecastService(db, user.business_id)
    return await svc.forecast()


# ---------- M5.1 OCR / M5.2 Voice (engine-gated) ----------

@router.post("/ocr")
async def ocr_document(
    file: UploadFile = File(...), user: User = Depends(get_current_user),
):
    proc = get_document_processor()
    data = await file.read()
    try:
        result = await proc.ocr(data, file.content_type or "application/octet-stream")
    except NotImplementedError as e:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(e))
    return result


@router.post("/voice/transcribe")
async def transcribe_voice(
    file: UploadFile = File(...), user: User = Depends(get_current_user),
):
    proc = get_voice_processor()
    data = await file.read()
    try:
        result = await proc.transcribe(data, file.content_type or "application/octet-stream")
    except NotImplementedError as e:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(e))
    return result
