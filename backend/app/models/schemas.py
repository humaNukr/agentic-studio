from pydantic import BaseModel, Field
from typing import List, Optional

class Message(BaseModel):
    role: str = Field(..., description="The role of the message sender (user, assistant, system)")
    content: str = Field(..., description="The actual text content of the message")
    embedding: Optional[List[float]] = Field(
        default=None,
        description="Vector representation of the text for semantic search"
    )

class ChatRequest(BaseModel):
    session_id: str = Field(..., description="Unique identifier for the chat session")
    prompt: str = Field(..., description="User input text")
    webhook_url: Optional[str] = Field(
        default=None,
        description="Optional URL to receive the asynchronous result"
    )