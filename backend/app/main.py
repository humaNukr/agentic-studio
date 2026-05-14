from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import google.generativeai as genai
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from app.core.optimizer import optimize_context
from app.core.config import settings
from app.models.schemas import Message
from app.models.documents import ChatSession


if not hasattr(AsyncIOMotorClient, "append_metadata"):
    AsyncIOMotorClient.append_metadata = lambda self, *args, **kwargs: None

# --- Життєвий цикл (Підключення до БД) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    client = AsyncIOMotorClient(settings.mongo_uri)
    await init_beanie(database=client.agentic_studio, document_models=[ChatSession])
    print("✅ MongoDB connected successfully")
    yield
    client.close()
    print("🛑 MongoDB connection closed")

app = FastAPI(title="Agentic Studio API", lifespan=lifespan)

# --- Ініціалізація LLM ---
genai.configure(api_key=settings.gemini_api_key)
llm_client = genai.GenerativeModel('gemini-2.5-flash')

class ChatRequest(BaseModel):
    session_id: str
    prompt: str

@app.post("/test-chat")
async def test_chat_with_memory(request: ChatRequest):
    # 1. Читаємо сесію з БД
    chat_session = await ChatSession.find_one(ChatSession.session_id == request.session_id)
    if not chat_session:
        chat_session = ChatSession(session_id=request.session_id, messages=[])

    # 2. Додаємо нове повідомлення в ПОВНУ історію
    user_msg = Message(role="user", content=request.prompt)
    chat_session.messages.append(user_msg)

    # 3. ВИКЛИКАЄМО ОПТИМІЗАТОР (Магія тут)
    # Наприклад, залишаємо 1 перше повідомлення і 4 останніх
    optimized_history = optimize_context(chat_session.messages, anchors_count=1, recent_window=4)

    # 4. ШАР АДАПТЕРА: Конвертуємо для Google ТІЛЬКИ обрізаний масив
    gemini_messages = []
    for msg in optimized_history:
        if msg.role == "system":
            continue
        role = "model" if msg.role == "assistant" else "user"
        gemini_messages.append({
            "role": role,
            "parts": [msg.content]
        })

    try:
        response = await llm_client.generate_content_async(gemini_messages)
        answer_text = response.text

        # 5. Зберігаємо відповідь у ПОВНУ історію в БД
        assistant_msg = Message(role="assistant", content=answer_text)
        chat_session.messages.append(assistant_msg)
        await chat_session.save()

        return {
            "response": answer_text,
            "saved_messages_in_db": len(chat_session.messages),     # Скільки реально лежить у базі (буде рости)
            "sent_messages_to_llm": len(gemini_messages)            # Скільки ми відправили в гугл (ніколи не перевищить 5)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))