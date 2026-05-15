from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

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