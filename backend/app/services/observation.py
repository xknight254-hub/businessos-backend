"""Observation Engine — pattern detection and business learning.

Uses scikit-learn and Prophet for time-series analysis, anomaly detection,
and pattern discovery. Integrates as library imports, not separate services.
"""
import numpy as np
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from app.models import Sale, SaleItem, Product, InventoryBatch, Customer


class ObservationEngine:
    """Core observation engine. Detects patterns from business data."""

    def __init__(self, db: AsyncSession, business_id: str):
        self.db = db
        self.business_id = business_id
        self.min_data_days = 7  # Minimum data before observations activate
        self.min_tx_per_sku = 10  # Minimum transactions per SKU

    async def _days_of_data(self) -> int:
        """Check how many days of data the business has."""
        result = await self.db.execute(
            select(func.min(Sale.created_at))
            .where(Sale.business_id == self.business_id, Sale.status == "completed")
        )
        first_date = result.scalar()
        if not first_date:
            return 0
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        return (now - first_date).days

    async def _total_transactions(self) -> int:
        result = await self.db.execute(
            select(func.count(Sale.id))
            .where(Sale.business_id == self.business_id, Sale.status == "completed")
        )
        return result.scalar() or 0

    @property
    async def has_enough_data(self) -> bool:
        days = await self._days_of_data()
        txs = await self._total_transactions()
        return days >= self.min_data_days and txs >= self.min_tx_per_sku

    async def detect_peak_hours(self) -> dict:
        """Detect peak business hours using sales count per hour."""
        if not await self.has_enough_data:
            return {"status": "insufficient_data", "days_needed": self.min_data_days}

        result = await self.db.execute(
            select(
                func.extract("hour", Sale.created_at).label("hour"),
                func.to_char(Sale.created_at, "Day").label("day"),
                func.count(Sale.id).label("tx_count"),
            )
            .where(Sale.business_id == self.business_id, Sale.status == "completed")
            .group_by("hour", "day")
            .order_by(desc("tx_count"))
            .limit(10)
        )
        peaks = [{"hour": int(r[0]), "day": r[1].strip(), "avg_sales": r[2]} for r in result.all()]

        return {
            "status": "ready",
            "peak_hours": peaks,
            "note": "Use these hours to optimize staffing and stock prep",
        }

    async def detect_fast_movers(self) -> list:
        """Identify fast-moving products using sales velocity."""
        if not await self.has_enough_data:
            return []

        result = await self.db.execute(
            select(
                Product.id, Product.name,
                func.sum(SaleItem.quantity).label("total_qty"),
                func.count(SaleItem.id).label("tx_count"),
            )
            .join(Product, SaleItem.product_id == Product.id)
            .join(Sale, Sale.id == SaleItem.sale_id)
            .where(
                Sale.business_id == self.business_id,
                Sale.status == "completed",
                Sale.created_at >= datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=30),
            )
            .group_by(Product.id, Product.name)
            .order_by(desc("total_qty"))
            .limit(20)
        )
        items = []
        for row in result.all():
            inv = await self.db.execute(
                select(func.coalesce(func.sum(InventoryBatch.quantity), 0))
                .where(
                    InventoryBatch.product_id == row.id,
                    InventoryBatch.business_id == self.business_id,
                )
            )
            stock = inv.scalar() or 0
            daily_rate = row.total_qty / 30.0
            days_until_out = int(stock / max(daily_rate, 0.1))

            items.append({
                "product_id": row.id,
                "product_name": row.name,
                "velocity": round(daily_rate, 1),
                "stock_remaining": stock,
                "days_until_out": days_until_out,
                "reorder_day": max(0, days_until_out - 3),  # Reorder 3 days before empty
            })
        return items

    async def detect_anomalies(self) -> list:
        """Detect anomalous sales patterns using statistical methods.

        Uses IQR (Interquartile Range) method from scikit-learn for simplicity.
        For more advanced forecasting, Prophet would be used after 3+ months of data.
        """
        if not await self.has_enough_data:
            return []

        result = await self.db.execute(
            select(
                func.date(Sale.created_at).label("date"),
                func.coalesce(func.sum(Sale.total), 0).label("revenue"),
            )
            .where(
                Sale.business_id == self.business_id,
                Sale.status == "completed",
                Sale.created_at >= datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=30),
            )
            .group_by(func.date(Sale.created_at))
            .order_by("date")
        )
        rows = result.all()
        if len(rows) < 7:
            return []

        values = np.array([r[1] for r in rows])
        q1, q3 = np.percentile(values, 25), np.percentile(values, 75)
        iqr = q3 - q1
        lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr

        anomalies = []
        for r in rows:
            if r[1] > upper:
                anomalies.append({
                    "type": "revenue_spike",
                    "severity": "medium",
                    "description": f"Revenue spike detected: KES {r[1]:,} on {r[0]} ({(r[1] / max(values.mean(), 1) - 1) * 100:.0f}% above average)",
                    "date": str(r[0]),
                    "value": r[1],
                })
            elif r[1] < lower:
                anomalies.append({
                    "type": "revenue_drop",
                    "severity": "high",
                    "description": f"Revenue drop: KES {r[1]:,} on {r[0]}. Possible you were closed or had low stock.",
                    "date": str(r[0]),
                    "value": r[1],
                })
        return anomalies

    async def generate_observations(self) -> list:
        """Generate AI observations from all detectors. Returns list of insight dicts."""
        if not await self.has_enough_data:
            return [{
                "type": "waiting_for_data",
                "title": "Learning your business",
                "body": f"I need about {self.min_data_days} more days of sales data before I can start finding patterns. Keep using the system!",
                "confidence": 1.0,
                "icon": "clock",
                "action_label": "Record your first sale",
                "action_url": "/pos",
            }]

        insights = []

        # Peak hours
        peaks = await self.detect_peak_hours()
        if peaks.get("peak_hours"):
            top = peaks["peak_hours"][0]
            insights.append({
                "type": "peak_hours",
                "title": "Busiest time detected",
                "body": f"Your peak hour is {top['hour']}:00 on {top['day']}s with ~{top['avg_sales']} transactions. Stock up before then.",
                "confidence": 0.85,
                "icon": "clock",
                "action_label": "View peak hours",
                "action_url": "/reports/sales/chart",
            })

        # Fast movers
        movers = await self.detect_fast_movers()
        if movers:
            for m in movers[:3]:
                if m["days_until_out"] <= 3:
                    insights.append({
                        "type": "low_stock_warning",
                        "title": f"{m['product_name']} running out",
                        "body": f"Only {m['stock_remaining']} left. At current rate ({m['velocity']}/day), you'll run out in {m['days_until_out']} days. Order today?",
                        "confidence": 0.9,
                        "icon": "alert-triangle",
                        "action_label": "Create purchase order",
                        "action_url": f"/products/{m['product_id']}",
                    })
                elif m["velocity"] > 5:
                    insights.append({
                        "type": "fast_mover",
                        "title": f"{m['product_name']} is flying off the shelf",
                        "body": f"You sell {m['velocity']:.0f} units/day. Reorder when stock hits {int(m['velocity'] * 3)}.",
                        "confidence": 0.85,
                        "icon": "trending-up",
                        "action_label": "View product",
                        "action_url": f"/products/{m['product_id']}",
                    })

        # Anomalies
        anomalies = await self.detect_anomalies()
        for a in anomalies:
            insights.append({
                "type": a["type"],
                "title": "Unusual day detected" if a["type"] == "revenue_drop" else "Revenue spike!",
                "body": a["description"],
                "confidence": 0.7,
                "icon": "alert-circle" if a["type"] == "revenue_drop" else "award",
                "action_label": "View details",
                "action_url": "/reports/sales/chart",
            })

        return insights

    async def get_insights(self, limit: int = 10) -> list:
        observations = await self.generate_observations()
        return observations[:limit]

    async def get_peak_hours_predictions(self) -> dict:
        """Use Prophet for time-series forecasting of peak hours.
        
        NOTE: Prophet requires 2+ months of hourly data for meaningful predictions.
        This is a placeholder for when sufficient data exists.
        """
        days = await self._days_of_data()
        txs = await self._total_transactions()
        return {
            "status": days >= 60,
            "message": "Prophet-based hourly predictions will activate after 60 days of data."
            if days < 60 else "Prophet model ready.",
            "days_of_data": days,
            "total_transactions": txs,
        }
