from typing import List
from beanie import Document
from pydantic import Field
from datetime import datetime, timezone
from app.models.schemas import Message  # Твій існуючий DTO

class ChatSession(Document):
    """
    Модель для колекції chat_sessions у MongoDB.
    Успадкування від Document (Beanie) автоматично дає нам CRUD методи (insert, find, save).
    """
    session_id: str
    messages: List[Message] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "chat_sessions"  # Назва колекції в базі