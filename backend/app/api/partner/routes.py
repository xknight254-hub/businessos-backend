from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.api.auth.dependencies import get_current_user
from app.models import User
from app.services.partner import BusinessPartner
from app.schemas.chat import ChatRequest

router = APIRouter(prefix="/partner", tags=["AI Business Partner"])


@router.post("/chat")
async def chat(
    req: ChatRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Chat with the AI Business Partner."""
    partner = BusinessPartner(db, user.business_id)
    return await partner.chat(
        message=req.message,
        conversation_id=req.conversation_id,
    )


@router.get("/capabilities")
async def capabilities():
    """List what the AI Business Partner can do."""
    return {
        "capabilities": [
            {"id": "health_score", "name": "Business Health Score", "description": "Check your 0-100 business health score"},
            {"id": "sales_summary", "name": "Sales Summary", "description": "Today, weekly, and monthly revenue"},
            {"id": "low_stock", "name": "Low Stock Alerts", "description": "Products that need reordering"},
            {"id": "fast_movers", "name": "Top Products", "description": "Your best-selling products"},
            {"id": "customer_insights", "name": "Customer Insights", "description": "Customer segments and credit"},
            {"id": "anomalies", "name": "Anomaly Detection", "description": "Unusual revenue patterns"},
            {"id": "memory_search", "name": "Business Memory", "description": "Search past conversations and patterns"},
        ],
        "languages": ["English", "Swahili", "Sheng (mixed)"],
        "llm_enabled": False,  # Will be true when API key is configured
    }
