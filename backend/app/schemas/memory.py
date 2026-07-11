from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime


class MemoryEntryCreate(BaseModel):
    content: str
    source: str = "observation"  # observation, pattern, correction, document, conversation
    memory_type: str = "episodic"  # episodic, semantic, procedural
    tags: Optional[List[str]] = None
    confidence: float = 0.5
    metadata: Optional[dict] = None


class MemoryEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    business_id: str
    content: str
    source: str
    memory_type: str
    tags: Optional[List[str]] = None
    confidence: float
    metadata: Optional[dict] = None
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    created_at: datetime


class MemorySearchResponse(BaseModel):
    items: List[dict]  # {id, content, source, memory_type, confidence, score, metadata, created_at}
    total: int


class MemoryQuery(BaseModel):
    query: str
    limit: int = 10
    memory_type: Optional[str] = None
    source: Optional[str] = None
    min_confidence: float = 0.0
    tags: Optional[List[str]] = None


class BusinessMemoryStats(BaseModel):
    total_entries: int
    by_type: dict
    by_source: dict
    top_tags: List[dict]
    oldest_entry: Optional[datetime]
    newest_entry: Optional[datetime]
