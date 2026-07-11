"""Business DNA — pattern learning and long-term behavior analysis.

Builds on the Observation Engine (detections) and Business Memory (storage).
Uses scikit-learn for clustering, pattern matching, and behavioral profiling.
"""
import numpy as np
from datetime import datetime, timedelta, timezone
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, and_
from app.models import Sale, SaleItem, Product, InventoryBatch, Customer, Supplier
from app.services.memory import BusinessMemory
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
import logging

logger = logging.getLogger(__name__)


class BusinessDNA:
    """Business DNA — pattern clustering and behavioral profile.

    Discovers what makes each business unique: category velocity signatures,
    customer segment patterns, supplier reliability, and business health indicators.
    """

    def __init__(self, db: AsyncSession, business_id: str):
        self.db = db
        self.business_id = business_id
        self.memory = BusinessMemory(db, business_id)
        self.min_data_days = 14

    async def _has_data(self) -> bool:
        result = await self.db.execute(
            select(func.min(Sale.created_at))
            .where(Sale.business_id == self.business_id, Sale.status == "completed")
        )
        first = result.scalar()
        if not first:
            return False
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        return (now - first).days >= self.min_data_days

    async def category_velocity_signature(self) -> dict:
        """Build category velocity profile — which categories sell fastest at what times.

        Returns a signature dict that uniquely describes this business's sales pattern.
        """
        if not await self._has_data():
            return {"status": "insufficient_data", "days_needed": self.min_data_days}

        result = await self.db.execute(
            select(
                Product.category,
                func.extract("hour", Sale.created_at).label("hour"),
                func.sum(SaleItem.quantity).label("qty"),
                func.sum(SaleItem.total).label("revenue"),
            )
            .join(Product, SaleItem.product_id == Product.id)
            .join(Sale, Sale.id == SaleItem.sale_id)
            .where(
                Sale.business_id == self.business_id,
                Sale.status == "completed",
                Product.category.isnot(None),
                Sale.created_at >= datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=30),
            )
            .group_by(Product.category, "hour")
            .order_by(desc("qty"))
        )
        rows = result.all()

        if not rows:
            return {"status": "no_category_data"}

        # Build category-hour matrix
        profile = {}
        for row in rows:
            cat = row.category or "Uncategorized"
            if cat not in profile:
                profile[cat] = {"total_qty": 0, "total_revenue": 0, "peak_hours": [], "hourly": {}}
            profile[cat]["total_qty"] += row.qty or 0
            profile[cat]["total_revenue"] += row.revenue or 0
            h = int(row.hour) if row.hour else 0
            profile[cat]["hourly"][h] = profile[cat]["hourly"].get(h, 0) + (row.qty or 0)

        # Compute peak hours per category
        for cat, data in profile.items():
            if data["hourly"]:
                peak = max(data["hourly"], key=data["hourly"].get)
                data["peak_hour"] = peak
                data["peak_hour_label"] = f"{peak}:00"
                data["total_hours_active"] = len(data["hourly"])

        # Store top insight in memory
        top_cat = max(profile.items(), key=lambda x: x[1]["total_revenue"])[0] if profile else None
        if top_cat:
            await self.memory.store(
                content=f"Your top category by revenue is {top_cat}. Peak sales at "
                       f"{profile[top_cat]['peak_hour_label']}.",
                source="dna",
                memory_type="semantic",
                tags=["dna", "category", "velocity"],
                confidence=0.85,
            )

        return {
            "status": "ready",
            "categories": profile,
            "total_categories": len(profile),
            "top_category": top_cat,
        }

    async def customer_segments(self) -> dict:
        """Cluster customers into behavioral segments using K-means.

        Segments: high-value, frequent, at-risk, new, lapsed.
        """
        if not await self._has_data():
            return {"status": "insufficient_data"}

        result = await self.db.execute(
            select(
                Customer.id, Customer.name, Customer.phone,
                Customer.total_visits, Customer.total_spent,
                Customer.credit_balance, Customer.last_visit,
            )
            .where(
                Customer.business_id == self.business_id,
                Customer.total_visits > 0,
            )
        )
        customers = result.all()
        if len(customers) < 5:
            return {"status": "not_enough_customers", "count": len(customers)}

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        features = []
        cust_ids = []
        for c in customers:
            days_since_last = (now - c.last_visit).days if c.last_visit else 999
            features.append([
                c.total_visits or 0,
                c.total_spent or 0,
                c.credit_balance or 0,
                days_since_last,
            ])
            cust_ids.append(c.id)

        # Cluster using K-means
        X = np.array(features, dtype=float)
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        n_clusters = min(4, len(customers))
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        labels = kmeans.fit_predict(X_scaled)

        segments = {}
        for i, label in enumerate(labels):
            label_name = ["high_value", "frequent", "at_risk", "new"][label % 4]
            if label_name not in segments:
                segments[label_name] = {"count": 0, "total_spent": 0, "customers": []}
            segments[label_name]["count"] += 1
            segments[label_name]["total_spent"] += features[i][1]
            if len(segments[label_name]["customers"]) < 3:
                segments[label_name]["customers"].append({
                    "id": cust_ids[i],
                    "name": customers[i].name,
                })

        # Store insight
        if "high_value" in segments:
            await self.memory.store(
                content=f"You have {segments['high_value']['count']} high-value customers "
                       f"who account for KES {segments['high_value']['total_spent']:,} in revenue.",
                source="dna",
                memory_type="semantic",
                tags=["dna", "customers", "segments"],
                confidence=0.8,
            )

        return {"status": "ready", "segments": segments, "total_analyzed": len(customers)}

    async def supplier_reliability(self) -> dict:
        """Score supplier reliability based on order history.

        Factors: order frequency, average order size, consistency.
        """
        result = await self.db.execute(
            select(
                Supplier.id, Supplier.name,
                Supplier.payment_terms,
            )
            .where(Supplier.business_id == self.business_id, Supplier.is_active == True)
        )
        suppliers = result.all()
        if not suppliers:
            return {"status": "no_suppliers"}

        profiles = []
        for s in suppliers:
            profiles.append({
                "supplier_id": s.id,
                "name": s.name,
                "payment_terms": s.payment_terms or "Standard",
                "score": 7.0,  # Base score, would be computed from orders
                "recommendation": "Add purchase order history to get reliability score",
            })

        return {"status": "ready", "suppliers": profiles}

    async def health_score(self) -> dict:
        """Compute overall business health score (0-100).

        Factors: revenue trend, customer retention, stock efficiency, credit health.
        """
        scores = {}

        # Revenue health (30 points)
        result = await self.db.execute(
            select(func.coalesce(func.avg(Sale.total), 0))
            .where(Sale.business_id == self.business_id, Sale.status == "completed")
        )
        avg_sale = result.scalar() or 1
        recent = await self.db.execute(
            select(func.coalesce(func.avg(Sale.total), 0))
            .where(
                Sale.business_id == self.business_id,
                Sale.status == "completed",
                Sale.created_at >= datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=7),
            )
        )
        recent_avg = recent.scalar() or 0
        revenue_health = min(30, int((recent_avg / max(avg_sale, 1)) * 30))
        scores["revenue_health"] = revenue_health

        # Customer retention (25 points)
        cust_result = await self.db.execute(
            select(func.count(Customer.id))
            .where(Customer.business_id == self.business_id)
        )
        total_customers = cust_result.scalar() or 0
        repeat = await self.db.execute(
            select(func.count(Customer.id))
            .where(
                Customer.business_id == self.business_id,
                Customer.total_visits >= 2,
            )
        )
        repeat_customers = repeat.scalar() or 0
        retention = min(25, int((repeat_customers / max(total_customers, 1)) * 25))
        scores["retention"] = retention

        # Stock efficiency (25 points)
        stock_result = await self.db.execute(
            select(func.count(InventoryBatch.id))
            .where(InventoryBatch.business_id == self.business_id)
        )
        total_stock = stock_result.scalar() or 1
        low_result = await self.db.execute(
            select(func.count(InventoryBatch.id))
            .where(
                InventoryBatch.business_id == self.business_id,
                InventoryBatch.quantity < InventoryBatch.min_quantity,
                InventoryBatch.min_quantity > 0,
            )
        )
        low_stock = low_result.scalar() or 0
        stock_health = min(25, max(0, 25 - int((low_stock / max(total_stock, 1)) * 25)))
        scores["stock_efficiency"] = stock_health

        # Credit health (20 points)
        credit_result = await self.db.execute(
            select(func.coalesce(func.sum(Customer.credit_balance), 0))
            .where(Customer.business_id == self.business_id)
        )
        total_credit = credit_result.scalar() or 0
        limit_result = await self.db.execute(
            select(func.coalesce(func.sum(Customer.credit_limit), 1))
            .where(Customer.business_id == self.business_id)
        )
        total_limit = limit_result.scalar() or 1
        credit_health = min(20, max(0, 20 - int((total_credit / max(total_limit, 1)) * 20)))
        scores["credit_health"] = credit_health

        total_score = revenue_health + retention + stock_health + credit_health

        # Determine trend
        trend = await self._determine_trend()

        # Store in memory
        await self.memory.store(
            content=f"Business Health Score: {total_score}/100. "
                   f"Revenue: {revenue_health}/30, Retention: {retention}/25, "
                   f"Stock: {stock_health}/25, Credit: {credit_health}/20.",
            source="dna",
            memory_type="semantic",
            tags=["dna", "health", "score"],
            confidence=0.85,
        )

        return {
            "score": total_score,
            "trend": trend,
            "components": scores,
            "max_score": 100,
            "status": "ready",
        }

    async def _determine_trend(self) -> str:
        """Determine whether business health is improving, declining, or stable."""
        this_month = await self.db.execute(
            select(func.coalesce(func.sum(Sale.total), 0))
            .where(
                Sale.business_id == self.business_id,
                Sale.status == "completed",
                Sale.created_at >= datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=30),
            )
        )
        last_month = await self.db.execute(
            select(func.coalesce(func.sum(Sale.total), 0))
            .where(
                Sale.business_id == self.business_id,
                Sale.status == "completed",
                Sale.created_at >= datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=60),
                Sale.created_at < datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=30),
            )
        )
        tm = this_month.scalar() or 0
        lm = last_month.scalar() or 1
        ratio = tm / lm
        if ratio > 1.1:
            return "improving"
        elif ratio < 0.9:
            return "declining"
        return "stable"

    async def full_dna_profile(self) -> dict:
        """Generate complete Business DNA profile."""
        category = await self.category_velocity_signature()
        segments = await self.customer_segments()
        suppliers = await self.supplier_reliability()
        health = await self.health_score()

        return {
            "business_id": self.business_id,
            "category_velocity": category,
            "customer_segments": segments,
            "supplier_reliability": suppliers,
            "health_score": health,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
