from fastapi import APIRouter, Depends, HTTPException
from app.core.exceptions import NotFoundError, ConflictError, BadRequestError, ForbiddenError, UnauthorizedError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.core.database import get_db
from app.api.auth.dependencies import get_current_user
from app.models import User, AutomationRule, AutomationLog
from app.services.automation import AutomationEngine
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/automation", tags=["Automation"])


class RuleCreate(BaseModel):
    name: str
    trigger_type: str  # low_stock, credit_overdue, daily_report, anomaly
    condition_config: Optional[dict] = None
    action_type: str  # send_notification, create_alert
    action_config: Optional[dict] = None


class RuleUpdate(BaseModel):
    name: Optional[str] = None
    is_enabled: Optional[bool] = None
    condition_config: Optional[dict] = None
    action_config: Optional[dict] = None


@router.get("/rules")
async def list_rules(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(AutomationRule)
        .where(AutomationRule.business_id == user.business_id)
        .order_by(AutomationRule.created_at.desc())
    )
    rules = []
    for r in result.scalars().all():
        rules.append({
            "id": r.id, "name": r.name, "trigger_type": r.trigger_type,
            "action_type": r.action_type, "is_enabled": r.is_enabled,
            "last_triggered": r.last_triggered, "trigger_count": r.trigger_count,
            "created_at": r.created_at,
        })
    return {"items": rules, "total": len(rules)}


@router.post("/rules")
async def create_rule(
    req: RuleCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    import json
    rule = AutomationRule(
        business_id=user.business_id,
        name=req.name,
        trigger_type=req.trigger_type,
        condition_config=json.dumps(req.condition_config) if req.condition_config else None,
        action_type=req.action_type,
        action_config=json.dumps(req.action_config) if req.action_config else None,
    )
    db.add(rule)
    await db.flush()
    return {
        "id": rule.id, "name": rule.name, "trigger_type": rule.trigger_type,
        "action_type": rule.action_type, "is_enabled": rule.is_enabled,
    }


@router.patch("/rules/{rule_id}")
async def update_rule(
    rule_id: str, req: RuleUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    import json
    result = await db.execute(
        select(AutomationRule).where(
            AutomationRule.id == rule_id,
            AutomationRule.business_id == user.business_id,
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise NotFoundError("Rule not found")
    if req.name is not None: rule.name = req.name
    if req.is_enabled is not None: rule.is_enabled = req.is_enabled
    if req.condition_config is not None:
        rule.condition_config = json.dumps(req.condition_config)
    if req.action_config is not None:
        rule.action_config = json.dumps(req.action_config)
    await db.flush()
    return {"status": "updated"}


@router.delete("/rules/{rule_id}", status_code=204)
async def delete_rule(
    rule_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(AutomationRule).where(
            AutomationRule.id == rule_id,
            AutomationRule.business_id == user.business_id,
        )
    )
    rule = result.scalar_one_or_none()
    if not rule:
        raise NotFoundError("Rule not found")
    await db.delete(rule)
    await db.flush()


@router.post("/templates")
async def seed_default_templates(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create default automation templates for this business."""
    engine = AutomationEngine(db, user.business_id)
    count = await engine.seed_default_rules()
    return {"seeded": count, "message": f"{count} automation rules created"}


@router.post("/run")
async def run_automation(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Run all enabled automation rules."""
    engine = AutomationEngine(db, user.business_id)
    results = await engine.run_all()
    return {"results": results, "total": len(results)}


@router.get("/logs")
async def automation_logs(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(AutomationLog)
        .where(AutomationLog.business_id == user.business_id)
        .order_by(desc(AutomationLog.created_at))
        .limit(limit)
    )
    logs = []
    for l in result.scalars().all():
        logs.append({
            "id": l.id, "rule_id": l.rule_id,
            "trigger_type": l.trigger_type, "action_type": l.action_type,
            "status": l.status, "details": l.details, "created_at": l.created_at,
        })
    return {"items": logs, "total": len(logs)}


@router.get("/suggestions")
async def automation_suggestions(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Suggest automation rules based on current business state."""
    engine = AutomationEngine(db, user.business_id)
    return await engine.suggest_rules()
