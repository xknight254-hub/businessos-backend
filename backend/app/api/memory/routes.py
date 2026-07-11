from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.api.auth.dependencies import get_current_user
from app.models import User
from app.services.memory import BusinessMemory
from app.schemas.memory import MemoryEntryCreate, MemoryQuery
from typing import Optional

router = APIRouter(prefix="/memory", tags=["Business Memory"])


@router.post("")
async def store_memory(
    req: MemoryEntryCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Store a new memory entry."""
    memory = BusinessMemory(db, user.business_id)
    entry = await memory.store(
        content=req.content,
        source=req.source,
        memory_type=req.memory_type,
        tags=req.tags,
        confidence=req.confidence,
        metadata=req.metadata,
    )
    return entry


@router.post("/search")
async def search_memory(
    req: MemoryQuery,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Semantic search over business memory."""
    memory = BusinessMemory(db, user.business_id)
    results = await memory.search(
        query=req.query,
        limit=req.limit,
        memory_type=req.memory_type,
        source=req.source,
        min_confidence=req.min_confidence,
        tags=req.tags,
    )
    return {"items": results, "total": len(results)}


@router.get("/stats")
async def memory_stats(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get memory usage statistics."""
    memory = BusinessMemory(db, user.business_id)
    return await memory.stats()


@router.post("/consolidate")
async def consolidate(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Consolidate memory — prune stale, promote patterns."""
    memory = BusinessMemory(db, user.business_id)
    return await memory.consolidate()


@router.get("/recent")
async def recent_memories(
    limit: int = Query(20, ge=1, le=100),
    source: Optional[str] = Query(None),
    memory_type: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get recent memory entries."""
    from sqlalchemy import select, desc, and_
    from app.models import BusinessMemory as MemoryModel

    conditions = [MemoryModel.business_id == user.business_id]
    if source:
        conditions.append(MemoryModel.source == source)
    if memory_type:
        conditions.append(MemoryModel.memory_type == memory_type)

    result = await db.execute(
        select(MemoryModel)
        .where(and_(*conditions))
        .order_by(desc(MemoryModel.created_at))
        .limit(limit)
    )
    items = []
    for entry in result.scalars().all():
        items.append({
            "id": entry.id,
            "content": entry.content,
            "source": entry.source,
            "memory_type": entry.memory_type,
            "confidence": (entry.confidence or 0) / 100.0,
            "tags": entry.tags.split(",") if entry.tags else [],
            "access_count": entry.access_count or 0,
            "created_at": entry.created_at,
        })
    return {"items": items, "total": len(items)}
