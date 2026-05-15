from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_agent_for_user,
    get_current_agent_from_api_key,
    get_current_user,
)
from app.core.database import get_db
from app.models import Agent, ApiKey, User
from app.schemas.agent import (
    AgentCreate,
    AgentResponse,
    ApiKeyCreate,
    ApiKeyResponse,
    ChatRequest,
    ChatResponse,
)
from app.services.api_keys import api_key_display_prefix, generate_api_key, hash_api_key
from app.services.packager import build_agent_zip

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/agents", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
def create_agent(
    payload: AgentCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Agent:
    agent = Agent(
        user_id=user.id,
        name=payload.name,
        description=payload.description,
        system_prompt=payload.system_prompt,
        tools=payload.tools,
        tool_policy=payload.tool_policy,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


@router.get("/agents", response_model=list[AgentResponse])
def list_agents(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Agent]:
    return list(
        db.scalars(
            select(Agent)
            .where(Agent.user_id == user.id)
            .order_by(Agent.created_at.desc())
        )
    )


@router.post("/agents/{agent_id}/api-keys", response_model=ApiKeyResponse)
def create_agent_api_key(
    payload: ApiKeyCreate,
    agent: Agent = Depends(get_agent_for_user),
    db: Session = Depends(get_db),
) -> ApiKeyResponse:
    raw_key = generate_api_key()
    api_key = ApiKey(
        user_id=agent.user_id,
        agent_id=agent.id,
        name=payload.name,
        key_hash=hash_api_key(raw_key),
        key_prefix=api_key_display_prefix(raw_key),
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)

    return ApiKeyResponse(
        id=api_key.id,
        name=api_key.name,
        key=raw_key,
        key_prefix=api_key.key_prefix,
        agent_id=api_key.agent_id,
        created_at=api_key.created_at,
    )


@router.post("/chat", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    agent: Agent = Depends(get_current_agent_from_api_key),
) -> ChatResponse:
    return ChatResponse(
        agent_id=agent.id,
        agent_name=agent.name,
        message=payload.message,
        response=(
            "Chat routing is configured. The LLM/ReAct engine can now use this "
            "agent config as its integration point."
        ),
    )


@router.get("/agents/{agent_id}/download")
def download_agent(agent: Agent = Depends(get_agent_for_user)) -> StreamingResponse:
    archive = build_agent_zip(agent)
    filename = f"agent-{agent.id}.zip"
    return StreamingResponse(
        archive,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
