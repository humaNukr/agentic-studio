from pydantic import BaseModel, Field
from typing import List, Optional

class Message(BaseModel):
    role: str = Field(..., description="The role of the message sender (user, assistant, system)")
    content: str = Field(..., description="The actual text content of the message")

    embedding: Optional[List[float]] = Field(
        default=None,
        description="Vector representation of text for semantic search"
    )

class ChatRequest(BaseModel):
    session_id: str
    prompt: str
    webhook_url: Optional[str] = Field(default=None, description="URL для відправки результату")