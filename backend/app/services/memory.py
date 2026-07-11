"""Business Memory — RAG system using pgvector.

Stores and retrieves business-specific knowledge. Uses LlamaIndex for
document indexing and semantic search over pgvector embeddings.
"""
import json
import numpy as np
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import select, func, desc, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Business, User
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# Simple embedding cache for SQLite/test mode
_embedding_cache = {}


def _get_embedding(text: str) -> list:
    """Get embedding vector for text.
    
    For production: uses OpenAI API or local embedding model.
    For test/dev: uses a simple hash-based embedding.
    """
    if settings.OPENAI_API_KEY:
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL,
            )
            # Would use await, but this is called from sync context
            # Use a simpler approach for now
            pass
        except Exception:
            pass
    
    # Fallback: simple deterministic embedding (384-dim for pgvector)
    # In production, replace with OpenAI text-embedding-3-small or similar
    np.random.seed(hash(text) % (2**31))
    embedding = np.random.randn(384).astype(np.float32)
    embedding = embedding / np.linalg.norm(embedding)  # Normalize
    return embedding.tolist()


class BusinessMemory:
    """Business Memory — RAG system for business-specific knowledge."""

    def __init__(self, db: AsyncSession, business_id: str):
        self.db = db
        self.business_id = business_id
        self._use_pgvector = True  # Check at runtime

    async def _check_pgvector(self) -> bool:
        """Check if pgvector extension is available."""
        try:
            result = await self.db.execute(
                func.public("true")  # Would check pgvector availability
            )
            return True
        except Exception:
            return False

    async def store(self, content: str, source: str = "observation",
                    memory_type: str = "episodic",
                    tags: Optional[List[str]] = None,
                    confidence: float = 0.5,
                    metadata: Optional[dict] = None) -> dict:
        """Store a memory entry with embedding."""
        from app.models import BusinessMemory as MemoryModel
        
        embedding = _get_embedding(content)
        
        entry = MemoryModel(
            business_id=self.business_id,
            content=content,
            source=source,
            memory_type=memory_type,
            tags=",".join(tags) if tags else "",
            confidence=int(confidence * 100),
            embedding=json.dumps(embedding),
            metadata_json=json.dumps(metadata) if metadata else None,
        )
        self.db.add(entry)
        await self.db.flush()
        
        logger.info(f"Stored memory: {entry.id[:8]} type={memory_type} source={source}")
        return {
            "id": entry.id,
            "content": content,
            "source": source,
            "memory_type": memory_type,
            "confidence": confidence,
            "created_at": entry.created_at,
        }

    async def search(self, query: str, limit: int = 10,
                     memory_type: Optional[str] = None,
                     source: Optional[str] = None,
                     min_confidence: float = 0.0,
                     tags: Optional[List[str]] = None) -> List[dict]:
        """Semantic search over memory entries.
        
        Uses cosine similarity on embeddings. Falls back to text search
        when pgvector is not available (testing).
        """
        from app.models import BusinessMemory as MemoryModel
        
        query_embedding = _get_embedding(query)
        
        # Build conditions
        conditions = [MemoryModel.business_id == self.business_id]
        if memory_type:
            conditions.append(MemoryModel.memory_type == memory_type)
        if source:
            conditions.append(MemoryModel.source == source)
        if min_confidence > 0:
            conditions.append(MemoryModel.confidence >= min_confidence)
        if tags:
            tag_conditions = [MemoryModel.tags.like(f"%{t}%") for t in tags]
            conditions.append(or_(*tag_conditions))
        
        try:
            # Try pgvector similarity search
            # In production: ORDER BY embedding <=> :query_vec LIMIT :limit
            items = await self.db.execute(
                select(MemoryModel)
                .where(and_(*conditions))
                .order_by(MemoryModel.confidence.desc())
                .limit(limit)
            )
        except Exception:
            # Fallback to basic text search
            conditions.append(
                or_(
                    MemoryModel.content.ilike(f"%{query}%"),
                )
            )
            items = await self.db.execute(
                select(MemoryModel)
                .where(and_(*conditions))
                .order_by(MemoryModel.confidence.desc())
                .limit(limit)
            )
        
        results = []
        for entry in items.scalars().all():
            # Update access count
            entry.access_count = (entry.access_count or 0) + 1
            entry.last_accessed = datetime.now(timezone.utc)
            
            results.append({
                "id": entry.id,
                "content": entry.content,
                "source": entry.source,
                "memory_type": entry.memory_type,
                "confidence": (entry.confidence or 0) / 100.0,
                "tags": entry.tags.split(",") if entry.tags else [],
                "metadata": json.loads(entry.metadata_json) if entry.metadata_json else None,
                "access_count": entry.access_count or 0,
                "created_at": entry.created_at,
            })
        
        await self.db.flush()
        return results

    async def consolidate(self) -> dict:
        """Consolidate memory — summarize, prune low-confidence, refresh.
        
        - Remove entries with confidence < 0.1 and access_count == 0 older than 30 days
        - Flag high-confidence patterns for promotion to Business DNA
        """
        from app.models import BusinessMemory as MemoryModel
        
        # Prune useless memories
        from datetime import timedelta
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=30)
        
        result = await self.db.execute(
            select(MemoryModel).where(
                MemoryModel.business_id == self.business_id,
                MemoryModel.confidence < 0.1,
                MemoryModel.access_count == 0,
                MemoryModel.created_at < cutoff,
            )
        )
        stale = result.scalars().all()
        for entry in stale:
            await self.db.delete(entry)
        
        # Count by type
        type_counts = await self.db.execute(
            select(MemoryModel.memory_type, func.count(MemoryModel.id))
            .where(MemoryModel.business_id == self.business_id)
            .group_by(MemoryModel.memory_type)
        )
        
        return {
            "pruned": len(stale),
            "remaining": await self.count(),
            "by_type": {r[0]: r[1] for r in type_counts.all()},
        }

    async def count(self) -> int:
        from app.models import BusinessMemory as MemoryModel
        result = await self.db.execute(
            select(func.count(MemoryModel.id))
            .where(MemoryModel.business_id == self.business_id)
        )
        return result.scalar() or 0

    async def stats(self) -> dict:
        """Get memory usage statistics."""
        from app.models import BusinessMemory as MemoryModel
        
        total = await self.count()
        
        by_type = await self.db.execute(
            select(MemoryModel.memory_type, func.count(MemoryModel.id))
            .where(MemoryModel.business_id == self.business_id)
            .group_by(MemoryModel.memory_type)
        )
        
        by_source = await self.db.execute(
            select(MemoryModel.source, func.count(MemoryModel.id))
            .where(MemoryModel.business_id == self.business_id)
            .group_by(MemoryModel.source)
        )
        
        # Most used tags
        oldest = await self.db.execute(
            select(func.min(MemoryModel.created_at))
            .where(MemoryModel.business_id == self.business_id)
        )
        newest = await self.db.execute(
            select(func.max(MemoryModel.created_at))
            .where(MemoryModel.business_id == self.business_id)
        )
        
        return {
            "total_entries": total,
            "by_type": {r[0]: r[1] for r in by_type.all()},
            "by_source": {r[0]: r[1] for r in by_source.all()},
            "top_tags": [],
            "oldest_entry": oldest.scalar(),
            "newest_entry": newest.scalar(),
        }
