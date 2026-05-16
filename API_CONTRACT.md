# API Contract — Frontend ↔ Backend

> Цей файл — закон. Frontend і Backend дотримуються цих форматів.
> Зміни — тільки після узгодження обох сторін.
> Контракт можна РОЗШИРЮВАТИ (додавати нові поля/endpoints), але не ЛАМАТИ існуючі.

---

## Base URL

```
Development: http://localhost:8000
Production:  https://api.studio.example.com
```

---

## 1. POST /api/v1/chat — відправити повідомлення агенту

Основний endpoint. Юзер пише → агент думає → стрімить відповідь.

### Request

```
POST /api/v1/chat
Content-Type: application/json

{
  "message": "What pods are running in production?",
  "session_id": "optional-uuid-for-conversation-history"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `message` | string | yes | Повідомлення юзера |
| `session_id` | string | no | Для збереження історії розмови. Якщо не передати — новий session. |

### Response — SSE Stream

```
Content-Type: text/event-stream
Cache-Control: no-cache
X-Accel-Buffering: no
```

Backend стрімить JSON events. Кожен event:

```
data: {"type": "thought", "content": "I need to check...", "metadata": {}}

data: {"type": "tool_call", "content": "Calling tool: web_search", "metadata": {"tool": "web_search", "args": {"query": "..."}}}

data: {"type": "tool_result", "content": "Result from web_search", "metadata": {"result": "Source: https://..."}}

data: {"type": "answer", "content": "Here are the results...", "metadata": {}}

data: {"type": "error", "content": "Agent stopped: Exceeded max iterations", "metadata": {}}
```

### Event Types

| type | Коли | Що показати на UI |
|------|------|-------------------|
| `thought` | LLM думає вголос | Сірий текст в thinking panel |
| `tool_call` | LLM вирішила викликати tool | "🔧 Calling: web_search" з аргументами |
| `tool_result` | Tool повернув результат | "📥 Result from web_search" (collapsed preview) |
| `answer` | Фінальна відповідь | Основний текст відповіді, великий, читабельний |
| `error` | Щось пішло не так | Червоне повідомлення з текстом помилки |

### Event Schema (Pydantic — вже існує в коді)

```python
class EventType(str, Enum):
    THOUGHT = "thought"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    ANSWER = "answer"
    ERROR = "error"

class AgentEvent(BaseModel):
    type: EventType
    content: str
    metadata: Optional[Dict[str, Any]] = {}
```

### Приклад повного потоку

```
User: "Search latest AI trends"

→ data: {"type": "thought", "content": "I'll search for the latest AI trends using web search."}
→ data: {"type": "tool_call", "content": "Calling tool: web_search", "metadata": {"tool": "web_search", "args": {"query": "latest AI trends 2026"}}}
→ data: {"type": "tool_result", "content": "Result from web_search", "metadata": {"result": "Source: https://... Content: AI agents are..."}}
→ data: {"type": "answer", "content": "Here are the latest AI trends for 2026:\n\n1. AI Agents..."}
```

---

## 2. GET /api/v1/health — healthcheck

### Request

```
GET /api/v1/health
```

### Response

```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

---

## 3. GET /api/v1/tools — список доступних інструментів

Frontend може показувати які tools є у агента.

### Request

```
GET /api/v1/tools
```

### Response

```json
{
  "tools": [
    {
      "name": "web_search",
      "description": "Searches for up-to-date information on the Internet"
    },
    {
      "name": "run_code",
      "description": "Executes Python code in a secure sandbox"
    }
  ]
}
```

---

## 4. Майбутні endpoints (v2 — розширення контракту)

Ці endpoints поки НЕ реалізовані, але контракт готовий для них.
Додавання нових endpoints НЕ ламає існуючі.

### POST /api/v1/agents/build — створити нового агента (Factory)

```
POST /api/v1/agents/build
Content-Type: application/json

{
  "prompt": "Create SRE agent for incidents",
  "model": "gpt-4o",
  "tools": ["shell", "pagerduty", "web_search"],   // optional override
  "ui_type": "chat_with_thinking"                   // optional
}
```

Response:
```json
{
  "id": "agent-uuid",
  "name": "sre-incident-agent",
  "status": "building",
  "stream_url": "/api/v1/agents/agent-uuid/stream"
}
```

### GET /api/v1/agents/{id}/stream — стрім збірки агента (SSE)

```
event: step
data: {"phase": "analyze", "message": "Analyzing your request..."}

event: thought
data: {"phase": "plan", "message": "Selected 5 tools..."}

event: clarification
data: {"message": "Кілька уточнень:", "questions": [
  {"id": "cluster_access", "type": "radio", "label": "Доступ до кластера", "options": [
    {"value": "readonly", "label": "Read-only", "default": true},
    {"value": "readwrite", "label": "Read-write"}
  ]}
]}

event: complete
data: {"agent_id": "agent-uuid", "download_url": "/api/v1/agents/agent-uuid/download"}
```

### POST /api/v1/agents/{id}/answers — відповіді на уточнення

```json
{
  "cluster_access": "readonly",
  "services": ["pagerduty", "datadog"]
}
```

### GET /api/v1/agents/{id}/download — скачати агента

Response: `application/gzip` — `.tar.gz` файл.

### GET /api/v1/agents — список агентів

```json
[
  {"id": "abc-123", "name": "sre-agent", "status": "ready", "created_at": "2026-05-16"},
  {"id": "def-456", "name": "marketing-agent", "status": "ready", "created_at": "2026-05-15"}
]
```

---

## SSE — як підключатись на Frontend

### JavaScript (vanilla)

```javascript
const response = await fetch('/api/v1/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ message: userMessage }),
});

const reader = response.body.getReader();
const decoder = new TextDecoder();
let buffer = '';

while (true) {
  const { done, value } = await reader.read();
  if (done) break;
  
  buffer += decoder.decode(value, { stream: true });
  const lines = buffer.split('\n');
  buffer = lines.pop() || '';
  
  for (const line of lines) {
    if (line.startsWith('data: ')) {
      const event = JSON.parse(line.slice(6));
      // event.type: "thought" | "tool_call" | "tool_result" | "answer" | "error"
      // event.content: текст
      // event.metadata: додаткові дані
      handleEvent(event);
    }
  }
}
```

### React Hook (рекомендовано)

```javascript
function useChat() {
  const [events, setEvents] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  
  const sendMessage = async (message) => {
    setIsLoading(true);
    setEvents([]);
    // ... fetch + stream parsing ...
    setIsLoading(false);
  };
  
  return { events, isLoading, sendMessage };
}
```

---

## CORS

Backend дозволяє:
```
Access-Control-Allow-Origin: http://localhost:5173  (Vite dev)
Access-Control-Allow-Methods: GET, POST
Access-Control-Allow-Headers: Content-Type
```

---

## Error Format

Всі помилки — однаковий формат:

```json
{
  "detail": "Human-readable error message"
}
```

HTTP коди:
| Code | Коли |
|------|------|
| 400 | Невалідний request (пустий message, невідомий tool) |
| 404 | Session/agent не знайдений |
| 429 | Rate limit exceeded |
| 500 | Internal server error |

---

## Розширюваність

Цей контракт спроектований для розширення:

1. **Нові event types** — додаємо в EventType enum. Frontend ігнорує невідомі types.
2. **Нові поля в metadata** — Frontend бере тільки те що знає, ігнорує решту.
3. **Нові endpoints** — додаємо поруч. Існуючі не змінюються.
4. **Нові query params** — додаємо як optional. Без них працює як раніше.

Правило: **додавати можна, видаляти/змінювати — ні** (без major version bump).
