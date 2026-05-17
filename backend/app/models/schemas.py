from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from enum import Enum

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


class EventType(str, Enum):
    THOUGHT = "thought"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    ANSWER = "answer"
    ERROR = "error"

class AgentEvent(BaseModel):
    type: EventType
    content: str
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

class AgentState(BaseModel):
    session_id: str
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    iteration_count: int = 0
