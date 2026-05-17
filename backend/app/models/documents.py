from typing import List
from beanie import Document
from pydantic import Field
from datetime import datetime, timezone
from app.models.schemas import Message

class ChatSession(Document):
    session_id: str
    messages: List[Message] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "chat_sessions"