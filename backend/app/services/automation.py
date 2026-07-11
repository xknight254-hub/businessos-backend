"""Automation Engine — rule-based triggers and actions.

Evaluates business conditions and executes automated actions.
Designed to be safe: suggestions only, never auto-executes financial actions.
"""
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models import AutomationRule, AutomationLog, Product, InventoryBatch, Customer, Sale
from app.services.observation import ObservationEngine

logger = logging.getLogger(__name__)


class AutomationEngine:
    """Evaluates rules and executes actions based on business state."""

    def __init__(self, db: AsyncSession, business_id: str):
        self.db = db
        self.business_id = business_id
        self.observation = ObservationEngine(db, business_id)

    async def seed_default_rules(self) -> int:
        """Create default automation templates if none exist."""
        result = await self.db.execute(
            select(func.count(AutomationRule.id))
            .where(AutomationRule.business_id == self.business_id)
        )
        if result.scalar() and result.scalar() > 0:
            return 0

        defaults = [
            AutomationRule(
                business_id=self.business_id,
                name="Low Stock Alert",
                trigger_type="low_stock",
                condition_config=json.dumps({"max_days_until_out": 3}),
                action_type="send_notification",
                action_config=json.dumps({"channel": "in_app", "severity": "warning"}),
            ),
            AutomationRule(
                business_id=self.business_id,
                name="Credit Overdue Reminder",
                trigger_type="credit_overdue",
                condition_config=json.dumps({"min_days_overdue": 7, "min_amount": 10000}),
                action_type="send_notification",
                action_config=json.dumps({"channel": "in_app", "severity": "info"}),
            ),
            AutomationRule(
                business_id=self.business_id,
                name="Daily Summary Report",
                trigger_type="daily_report",
                condition_config=json.dumps({"time": "07:00"}),
                action_type="send_notification",
                action_config=json.dumps({"channel": "morning_briefing"}),
            ),
            AutomationRule(
                business_id=self.business_id,
                name="Revenue Anomaly Alert",
                trigger_type="anomaly",
                condition_config=json.dumps({"severity": "high"}),
                action_type="send_notification",
                action_config=json.dumps({"channel": "in_app", "severity": "warning"}),
            ),
        ]
        for rule in defaults:
            self.db.add(rule)
        await self.db.flush()
        return len(defaults)

    async def evaluate_rule(self, rule: AutomationRule) -> bool:
        """Evaluate whether a rule's condition is met."""
        try:
            config = json.loads(rule.condition_config or "{}")
        except json.JSONDecodeError:
            config = {}

        if rule.trigger_type == "low_stock":
            max_days = config.get("max_days_until_out", 3)
            movers = await self.observation.detect_fast_movers()
            return any(m.get("days_until_out", 99) <= max_days for m in movers)

        elif rule.trigger_type == "credit_overdue":
            min_amount = config.get("min_amount", 10000)
            result = await self.db.execute(
                select(func.count(Customer.id))
                .where(
                    Customer.business_id == self.business_id,
                    Customer.credit_balance >= min_amount,
                )
            )
            return (result.scalar() or 0) > 0

        elif rule.trigger_type == "daily_report":
            return True

        elif rule.trigger_type == "anomaly":
            anomalies = await self.observation.detect_anomalies()
            threshold = config.get("severity", "high")
            return any(a.get("severity") == threshold for a in anomalies)

        return False

    async def execute_action(self, rule: AutomationRule) -> dict:
        """Execute an automation rule action."""
        import logging
        logger = logging.getLogger(__name__)

        detail = f"Triggered: {rule.trigger_type} → Action: {rule.action_type}"

        if rule.action_type == "send_notification":
            logger.info(f"[AUTO] {rule.name}: {detail}")
            return {"status": "success", "detail": detail}

        return {"status": "skipped", "detail": f"Unknown action type: {rule.action_type}"}

    async def run_all(self) -> List[dict]:
        """Evaluate and execute all enabled rules."""
        results = []
        result = await self.db.execute(
            select(AutomationRule).where(
                AutomationRule.business_id == self.business_id,
                AutomationRule.is_enabled == True,
            )
        )
        rules = result.scalars().all()

        for rule in rules:
            try:
                triggered = await self.evaluate_rule(rule)
                if triggered:
                    action_result = await self.execute_action(rule)
                    rule.last_triggered = datetime.now(timezone.utc).replace(tzinfo=None)
                    rule.trigger_count = (rule.trigger_count or 0) + 1

                    log = AutomationLog(
                        business_id=self.business_id,
                        rule_id=rule.id,
                        trigger_type=rule.trigger_type,
                        action_type=rule.action_type,
                        status=action_result.get("status", "success"),
                        details=action_result.get("detail", ""),
                    )
                    self.db.add(log)
                    results.append({
                        "rule_id": rule.id,
                        "rule_name": rule.name,
                        "triggered": True,
                        "status": action_result.get("status"),
                    })
                else:
                    results.append({
                        "rule_id": rule.id,
                        "rule_name": rule.name,
                        "triggered": False,
                        "status": "skipped",
                    })
            except Exception as e:
                logger.error(f"Rule {rule.name} failed: {e}")
                results.append({
                    "rule_id": rule.id, "rule_name": rule.name,
                    "triggered": True, "status": "failed", "error": str(e),
                })

        await self.db.flush()
        return results

    async def suggest_rules(self) -> List[dict]:
        """Suggest automation rules based on current business data."""
        suggestions = []

        # Check if business has products
        prod_result = await self.db.execute(
            select(func.count(Product.id))
            .where(Product.business_id == self.business_id)
        )
        has_products = (prod_result.scalar() or 0) > 0
        if has_products:
            suggestions.append({
                "trigger_type": "low_stock",
                "name": "Low Stock Alert",
                "description": "Get notified when products are running low (3 days or less)",
                "action_type": "send_notification",
            })

        # Check if business has customers with credit
        credit_result = await self.db.execute(
            select(func.count(Customer.id))
            .where(
                Customer.business_id == self.business_id,
                Customer.credit_balance > 0,
            )
        )
        has_credit = (credit_result.scalar() or 0) > 0
        if has_credit:
            suggestions.append({
                "trigger_type": "credit_overdue",
                "name": "Credit Overdue Reminder",
                "description": "Get daily reminders when customers have unpaid credit",
                "action_type": "send_notification",
            })

        # Check if business has sales
        sale_result = await self.db.execute(
            select(func.count(Sale.id))
            .where(Sale.business_id == self.business_id)
        )
        has_sales = (sale_result.scalar() or 0) > 0
        if has_sales:
            suggestions.append({
                "trigger_type": "daily_report",
                "name": "Morning Briefing",
                "description": "Get a daily summary of yesterday's sales every morning",
                "action_type": "send_notification",
            })

        if len(suggestions) < 2:
            suggestions.append({
                "trigger_type": "custom",
                "name": "Keep Recording Data",
                "description": "Add more products and sales to unlock automation suggestions",
                "action_type": "send_notification",
            })

        return suggestions
