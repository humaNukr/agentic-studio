from typing import List, Dict
from app.models.documents import ChatSession
from app.models.schemas import Message
from app.core.semantic_memory import semantic_service
from app.core.webhooks import send_webhook
from app.core.optimizer import optimize_context

class AgentStateManager:
    """
    Facade service for managing conversational state, vector memory, and notifications.
    This service is meant to be consumed by the Orchestrator layer.
    """

    @staticmethod
    async def get_or_create_session(session_id: str) -> ChatSession:
        session = await ChatSession.find_one(ChatSession.session_id == session_id)
        if not session:
            session = ChatSession(session_id=session_id, messages=[])
        return session

    @staticmethod
    async def add_message_and_get_context(session_id: str, role: str, content: str, optimize: bool = False) -> List[Dict]:
        """
        Saves a new message, generates its embedding, and returns the formatted history for the LLM.
        """
        session = await AgentStateManager.get_or_create_session(session_id)

        # Generate semantic embedding
        vector = await semantic_service.generate_embedding(content)

        # Save to DB
        new_message = Message(role=role, content=content, embedding=vector)
        session.messages.append(new_message)
        await session.save()

        # Prepare context
        history = session.messages
        if optimize:
            history = optimize_context(history)

        # Convert to LLM adapter format
        llm_messages = [
            {"role": "model" if m.role == "assistant" else "user", "parts": [m.content]}
            for m in history if m.role != "system"
        ]

        return llm_messages

    @staticmethod
    async def finish_turn(session_id: str, agent_response: str, webhook_url: str = None) -> None:
        """
        Saves the agent's final response and triggers the webhook if provided.
        """
        session = await AgentStateManager.get_or_create_session(session_id)

        vector = await semantic_service.generate_embedding(agent_response)
        new_message = Message(role="assistant", content=agent_response, embedding=vector)

        session.messages.append(new_message)
        await session.save()

        if webhook_url:
            await send_webhook(webhook_url, session_id, {"agent_reply": agent_response})

state_manager = AgentStateManager()