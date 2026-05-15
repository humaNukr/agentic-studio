from fastapi import Depends, Header, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models import Agent, ApiKey, User
from app.services.api_keys import hash_api_key


def get_current_user(db: Session = Depends(get_db)) -> User:
    user = db.scalar(select(User).where(User.email == settings.demo_user_email))
    if user is not None:
        return user

    user = User(email=settings.demo_user_email)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_agent_for_user(
    agent_id: int = Path(gt=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Agent:
    agent = db.scalar(
        select(Agent).where(
            Agent.id == agent_id,
            Agent.user_id == user.id,
        )
    )
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )
    return agent


def get_current_agent_from_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> Agent:
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
        )

    api_key = db.scalar(
        select(ApiKey).where(
            ApiKey.key_hash == hash_api_key(x_api_key),
            ApiKey.revoked_at.is_(None),
        )
    )
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    agent = db.get(Agent, api_key.agent_id)
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )
    return agent

