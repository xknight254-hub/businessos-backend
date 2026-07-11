from pydantic import BaseModel
from typing import Optional, List


class ChatMessage(BaseModel):
    role: str  # user, assistant
    content: str


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    conversation_id: str
    tool_used: Optional[str] = None
    confidence: float = 1.0
    suggestions: List[str] = []


class ConversationHistory(BaseModel):
    conversation_id: str
    messages: List[ChatMessage]
    created_at: str
    summary: Optional[str] = None
