from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
import google.generativeai as genai

from app.core.config import settings
from app.core.semantic_memory import semantic_service
from app.core.webhooks import send_webhook
from app.models.schemas import Message
from app.models.documents import ChatSession

# ==========================================
# 1. SETUP & WORKAROUNDS
# ==========================================

if not hasattr(AsyncIOMotorClient, "append_metadata"):
    AsyncIOMotorClient.append_metadata = lambda self, *args, **kwargs: None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages the application lifecycle, establishing and closing the database connection.
    """
    client = AsyncIOMotorClient(settings.mongo_uri)
    await init_beanie(database=client.agentic_studio, document_models=[ChatSession])
    yield
    client.close()

# ==========================================
# 2. APPLICATION & SERVICES INITIALIZATION
# ==========================================

app = FastAPI(title="Agentic Studio API", lifespan=lifespan)

genai.configure(api_key=settings.gemini_api_key)
llm_client = genai.GenerativeModel('gemini-2.5-flash')

# ==========================================
# 3. SCHEMAS (DTOs)
# ==========================================

class ChatRequest(BaseModel):
    session_id: str = Field(..., description="Unique identifier for the chat session.")
    prompt: str = Field(..., description="The user's input text.")
    webhook_url: Optional[str] = Field(default=None, description="Optional URL to receive the agent's response asynchronously.")

# ==========================================
# 4. BACKGROUND WORKERS
# ==========================================

async def agent_background_worker(request: ChatRequest):
    """
    Background worker that processes the user prompt, generates embeddings,
    communicates with the LLM, and sends the result via webhook.
    """
    try:
        chat_session = await ChatSession.find_one(ChatSession.session_id == request.session_id)
        if not chat_session:
            chat_session = ChatSession(session_id=request.session_id, messages=[])

        user_vector = await semantic_service.generate_embedding(request.prompt)
        chat_session.messages.append(Message(role="user", content=request.prompt, embedding=user_vector))

        gemini_messages = [
            {"role": "model" if m.role == "assistant" else "user", "parts": [m.content]}
            for m in chat_session.messages if m.role != "system"
        ]

        response = await llm_client.generate_content_async(gemini_messages)
        answer_text = response.text

        assistant_vector = await semantic_service.generate_embedding(answer_text)
        chat_session.messages.append(Message(role="assistant", content=answer_text, embedding=assistant_vector))
        await chat_session.save()

        if request.webhook_url:
            await send_webhook(
                webhook_url=request.webhook_url,
                session_id=request.session_id,
                payload={"agent_reply": answer_text}
            )

    except Exception as e:
        print(f"Background worker error: {e}")

# ==========================================
# 5. API ROUTES
# ==========================================

@app.post("/test-chat")
async def test_chat_with_memory(request: ChatRequest):
    """
    Synchronous endpoint for testing chat memory and embedding generation.
    Returns the LLM response directly.
    """
    chat_session = await ChatSession.find_one(ChatSession.session_id == request.session_id)
    if not chat_session:
        chat_session = ChatSession(session_id=request.session_id, messages=[])

    user_vector = await semantic_service.generate_embedding(request.prompt)
    chat_session.messages.append(Message(role="user", content=request.prompt, embedding=user_vector))
    await chat_session.save()

    gemini_messages = [
        {"role": "model" if m.role == "assistant" else "user", "parts": [m.content]}
        for m in chat_session.messages if m.role != "system"
    ]

    try:
        response = await llm_client.generate_content_async(gemini_messages)
        answer_text = response.text

        assistant_vector = await semantic_service.generate_embedding(answer_text)
        chat_session.messages.append(Message(role="assistant", content=answer_text, embedding=assistant_vector))
        await chat_session.save()

        return {
            "response": answer_text,
            "vector_dimension": len(user_vector)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/run-agent", status_code=202)
async def run_agent_endpoint(request: ChatRequest, background_tasks: BackgroundTasks):
    """
    Asynchronous endpoint that triggers the agent execution in the background
    and returns a 202 Accepted status immediately.
    """
    background_tasks.add_task(agent_background_worker, request)

    return {
        "status": "processing",
        "session_id": request.session_id,
        "message": "Agent execution started. Results will be sent to the provided webhook URL."
    }