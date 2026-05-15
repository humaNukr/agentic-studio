from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = ""
    system_prompt: str = Field(min_length=1)
    tools: list[str] = Field(default_factory=list)
    tool_policy: dict[str, Any] = Field(default_factory=dict)


class AgentResponse(BaseModel):
    id: int
    user_id: int
    name: str
    description: str
    system_prompt: str
    tools: list[str]
    tool_policy: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApiKeyCreate(BaseModel):
    name: str = Field(default="Default", min_length=1, max_length=160)


class ApiKeyResponse(BaseModel):
    id: int
    name: str
    key: str
    key_prefix: str
    agent_id: int
    created_at: datetime


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)


class ChatResponse(BaseModel):
    agent_id: int
    agent_name: str
    message: str
    response: str

