from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.api.auth.dependencies import get_current_user
from app.models import User
from app.services.dna import BusinessDNA

router = APIRouter(prefix="/dna", tags=["Business DNA"])


@router.get("/profile")
async def dna_profile(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Full Business DNA profile — categories, customers, suppliers, health."""
    dna = BusinessDNA(db, user.business_id)
    return await dna.full_dna_profile()


@router.get("/category-velocity")
async def category_velocity(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Category velocity signature — which categories sell fastest at what times."""
    dna = BusinessDNA(db, user.business_id)
    return await dna.category_velocity_signature()


@router.get("/customer-segments")
async def customer_segments(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Customer segmentation using K-means clustering."""
    dna = BusinessDNA(db, user.business_id)
    return await dna.customer_segments()


@router.get("/supplier-reliability")
async def supplier_reliability(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Supplier reliability scoring."""
    dna = BusinessDNA(db, user.business_id)
    return await dna.supplier_reliability()


@router.get("/health-score")
async def health_score(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Business health score (0-100) with component breakdown."""
    dna = BusinessDNA(db, user.business_id)
    return await dna.health_score()
