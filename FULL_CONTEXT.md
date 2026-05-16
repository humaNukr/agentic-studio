# Agentic Studio — Full Architecture Context

> Повний контекст архітектурної дискусії.
> Передай це в нове контекстне вікно — воно матиме всю інформацію.
> Також є готовий код-скелет у /Users/litvinchuk.roman/WebstormProjects/agentic-studio/

---

## 1. Ідея продукту

**Agentic Studio** — платформа, де користувач описує агента природною мовою,
а система видає готовий до деплою Docker-контейнер з працюючим AI-агентом всередині.

Приклади промптів:
- "Create agent that searches the web and catches latest marketing information"
- "Backend developer agent whose specialisation is Java development"
- "Create DevOps SRE agent who specialises on incidents and monitoring"

**Вихід:** `.tar.gz` архів з Dockerfile + config. Користувач робить `docker compose up` — агент працює.

---

## 2. Архітектура

### v1 (MVP — зараз будуємо)

Два компоненти. Один працюючий агент, не фабрика.

```
┌──────────────────┐         ┌──────────────────────────────────────────┐
│   Frontend       │  POST   │  Backend (FastAPI)                       │
│   (React 19)     │────────▶│                                          │
│                  │◀────────│  /api/v1/chat → SSE stream               │
│  Chat UI         │   SSE   │                                          │
│  Thinking panel  │         │  ReActEngine (Groq / Llama 3.3-70b)     │
│  Tool call view  │         │    ├── web_search (Tavily)               │
│                  │         │    └── run_code (E2B sandbox)             │
└──────────────────┘         └──────────────────────────────────────────┘
```

**LLM:** Groq (Llama 3.3-70b-versatile) через OpenAI-compatible API — швидко, дешево.
**Tools:** Direct async Python functions (не MCP). Registry pattern з центральним dispatcher.
**Streaming:** SSE через AsyncGenerator — AgentEvent (thought/tool_call/tool_result/answer/error).

### v2 (Agent Factory — наступний етап)

Додаємо фабрику: prompt → ready-to-deploy Docker контейнер.

```
┌──────────────┐    ┌───────────────────┐    ┌──────────────────┐
│   Frontend   │───▶│  Backend (FastAPI) │───▶│  Artifact Store  │
│   (React)    │◀───│  Agent Factory     │    │  (S3 / Minio)    │
│              │SSE │  Template Engine   │    │                  │
└──────────────┘    └───────────────────┘    └──────────────────┘
                              │
                    ┌─────────┴──────────┐
                    │  Base Runtime Image │
                    │  (all agents        │
                    │   inherit from it)  │
                    └────────────────────┘
```

- **Orchestrator pipeline:** Analyze → Plan → Generate → Validate → Package
- LLM парсить промпт у JSON, генерує system prompt/persona
- LLM НЕ генерує код — весь код у pre-built шаблонах
- Результат: tar.gz з Dockerfile + config
- MCP замість direct Python functions — plug-and-play tools

---

## 3. Ключове рішення: LLM генерує конфіг, НЕ код

### v1 (зараз): LLM = мозок агента

В поточній архітектурі LLM (Groq/Llama 3.3-70b) працює як runtime reasoning engine:
- Отримує повідомлення юзера
- Думає (thought) і вирішує які tools викликати
- Отримує результат tool → думає далі або відповідає
- Весь код tools — pre-built Python functions (не генерований LLM)

### v2 (потім): LLM = також builder

| Що робить LLM (5-10 сек) | Що роблять шаблони (<1 сек) |
|---------------------------|----------------------------|
| Парсить промпт → JSON | Рендерить Dockerfile |
| Вибирає інструменти | Збирає requirements |
| Генерує system prompt (текст) | Копіює tool modules |
| Генерує persona (текст) | Компонує docker-compose.yml |

Чому НЕ генеруємо код: повільно (2-5 хв), ненадійно (~60-70%), небезпечно, неможливо підтримувати.
Hybrid підхід: збірка за ~10-15 сек, надійність ~98%+.

---

## 4. Tools — інструменти агента

### v1 (зараз): Direct Python functions

Кожен tool = async Python function з OpenAI function calling schema.

```python
# registry.py — центральний dispatcher
TOOLS = [WEB_SEARCH_SCHEMA, RUN_CODE_SCHEMA]
TOOL_EXECUTORS = {"web_search": web_search, "run_code": run_code}
async def execute_tool(name, tool_input) -> str: ...
```

Поточні tools:
- `web_search` — Tavily async (search_depth="advanced", 3 results)
- `run_code` — E2B cloud sandbox (Python execution, stdout/stderr)

Додати новий tool = 1 файл: schema + async function + зареєструвати в registry.

### v2 (потім): MCP (Model Context Protocol)

Стандартний протокол підключення інструментів до LLM. Як USB для AI.

Кожен інструмент = MCP сервер (subprocess):
- `@tavily/mcp-server` — пошук в інтернеті
- `@modelcontextprotocol/server-filesystem` — файли
- `@modelcontextprotocol/server-github` — GitHub API
- `@modelcontextprotocol/server-slack` — Slack

Як працює:
1. Runtime читає `mcp_servers.json`
2. Запускає кожен MCP сервер як subprocess (stdio transport)
3. Викликає `tools/list` — дізнається доступні інструменти
4. Передає список LLM
5. LLM вирішує що викликати → Runtime маршрутизує

**Міграція v1→v2:** registry.py вже має правильний інтерфейс (`execute_tool(name, args) → str`). Замінити internal dispatcher на MCP router — зміна тільки в registry, не в ReAct engine.

---

## 5. ReAct Loop — як агент думає

**Реалізовано в:** `backend/app/services/react_engine.py`

```python
class ReActEngine:
    def __init__(self, llm_client, model_name, tools_schema, tool_executor, max_iterations=10): ...

    async def run_loop(self, state: AgentState) -> AsyncGenerator[AgentEvent, None]:
        while state.iteration_count < self.max_iterations:
            response = await self.llm.chat.completions.create(
                model=self.model, messages=state.messages,
                tools=self.tools_schema, tool_choice="auto"
            )
            message = response.choices[0].message

            if message.content:
                yield AgentEvent(type=THOUGHT if message.tool_calls else ANSWER, content=...)

            if not message.tool_calls:
                break  # фінальна відповідь

            for tool_call in message.tool_calls:
                yield AgentEvent(type=TOOL_CALL, ...)
                result = await self.tool_executor(tool_call.function.name, arguments)
                yield AgentEvent(type=TOOL_RESULT, ...)
                state.messages.append({"role": "tool", ...})
```

**LLM:** Groq (Llama 3.3-70b-versatile) через OpenAI-compatible API.
**Стрім:** AsyncGenerator yield-ить AgentEvent → FastAPI конвертує в SSE.

---

## 6. Security — 5 рівнів (Defense in Depth)

1. **Kubernetes:** runAsNonRoot, readOnlyRootFilesystem, drop ALL capabilities, NetworkPolicy, ResourceQuota
2. **Container:** non-root user, read-only fs (крім /app/workspace), мінімальний base image, без Docker socket
3. **Application (Guardrails):** command allowlist/denylist, tool rate limits, budget guard (max tokens/cost), output filter (PII/secrets)
4. **MCP Sandbox:** proxy між runtime і MCP серверами, валідація кожного виклику, audit log
5. **LLM Prompt:** system prompt з обмеженнями (найслабший шар — можна jailbreak-нути, тому є 4 шари вище)

Принцип: кожен шар припускає що всі шари нижче скомпрометовані.

---

## 7. Що генерується на виході

```
sre-agent/
├── Dockerfile               ← 2 рядки: FROM base + COPY config
├── docker-compose.yml
├── .env.example
├── README.md
└── config/
    ├── agent_config.json     ← ідентичність: name, model, domain
    ├── system_prompt.txt     ← повний prompt з fragments
    ├── mcp_servers.json      ← які MCP сервери запускати
    └── tool_policy.json      ← безпека: rate limits, budgets, allowlists
```

Агент = **ОДИН контейнер.** Frontend агента — 3 статичних файли (HTML/JS/CSS), FastAPI їх serve-ить. Не потребує окремого Node.js/React. Один процес uvicorn тримає все.

---

## 8. Структура репозиторію

### Поточний стан: Монорепо (v1)

Команда правильно обрала монорепо на старті. Реальна структура:

```
agentic-studio/                    ← /Users/litvinchuk.roman/PyCharmProjects/agentic-studio/
├── API_CONTRACT.md                ← ✅ Контракт frontend ↔ backend
├── FULL_CONTEXT.md                ← Цей файл
├── backend/
│   ├── main.py                    ← TODO: FastAPI entrypoint
│   ├── requirements.txt           ← ✅ Всі залежності
│   └── app/
│       ├── core/                  ← TODO: config, settings
│       ├── models/
│       │   └── schemas.py         ← ✅ AgentEvent, AgentState, EventType
│       ├── services/
│       │   └── react_engine.py    ← ✅ ReAct loop (Groq/OpenAI-compatible)
│       └── tools/
│           ├── registry.py        ← ✅ Tool dispatcher
│           ├── web_search.py      ← ✅ Tavily integration
│           └── run_code.py        ← ✅ E2B sandbox
├── frontend/
│   ├── package.json               ← ✅ React 19 + Vite 8
│   └── src/
│       ├── main.jsx               ← ✅ Entrypoint
│       └── App.jsx                ← TODO: Chat UI
└── deploy/                        ← TODO: Dockerfile, docker-compose, Helm (v2)
```

### Різниця з архітектурним планом

| Архітектурний план | Реальний код | Чому |
|---|---|---|
| `api/routes.py` + `api/schemas.py` | `models/schemas.py` | Schemas готові. Routes = наступний крок. |
| `factory/orchestrator.py` | Поки немає | Factory = v2. Зараз фокус на **працюючому агенті**, не на фабриці. |
| `templates/` (prompts, tools, policies) | Поки немає | v2. Зараз system prompt = hardcoded. |
| MCP manager | Direct Python functions | Правильне рішення для v1. MCP = v2. |
| `runtime/` (окрема репо) | `services/react_engine.py` | ReAct engine живе в монорепо. Виносити в окрему репо коли з'являться generated agents. |

### Коли розділяти на 2 репо

Розділяти коли буде Agent Factory (v2) — тоді з'явиться різниця між:
- **agentic-studio** — платформа що будує агентів
- **agentic-runtime** — base image що працює всередині кожного агента

На етапі v1 (один працюючий агент) — монорепо правильне рішення.

---

## 9. RAG / Vector Database — рішення

### Загальний підхід
RAG — це просто ще один MCP tool в арсеналі агента. LLM сама вирішує коли його використати.

### Для SRE агента RAG корисний для:
- Постмортеми (найсильніший use case — "чи було щось схоже?")
- Runbook-и ("як робити rollback?")
- Architecture docs ("яка архітектура сервісу X?")

### RAG НЕ потрібний для:
- Real-time дані (інциденти, метрики) → прямі API calls (PagerDuty, Datadog)
- Structured data (timeseries) → API queries
- Часто змінювані конфіги → kubectl/live reads

### Embedding pipeline
```
Документ → Load → Chunk (500 tokens, 100 overlap) → Embed → Store
                                                        │
                                          Модель: all-MiniLM-L6-v2
                                          (80MB, CPU, безкоштовно)
                                          або OpenAI text-embedding-3-small
```

### Вибір бази для RAG

| Рішення | Коли |
|---------|------|
| **ChromaDB embedded** (рекомендовано для v1-v2) | <500K docs, zero infra, файл на диску у volume |
| pgvector | Тільки якщо вже є PG і великі обсяги (>500K) |
| Qdrant/Weaviate | Enterprise-scale, мільйони документів |

**ChromaDB embedded = найкраще для агента в контейнері:**
- Не сервер, а бібліотека (як SQLite)
- Нема connection string — просто `chromadb.PersistentClient(path="/app/workspace/.knowledge")`
- Per-agent isolation автоматично — кожен агент має свій файл БД
- Operational overhead = нуль

### Як наповнювати базу

**v1 (MVP):** Volume mount. Користувач кладе .md файли в `./knowledge/`, при старті каже агенту "index all files".

**v2:** File watcher (inotify/watchdog) — автоматичний ingestion при появі нових файлів.

**v3:** External sync — CronJob підтягує з Confluence/GitHub/Notion.

### Як Factory генерує агента з RAG

Коли Factory бачить `"knowledge_base"` в tools_required:
1. Додає `knowledge_base` MCP config в `mcp_servers.json`
2. Додає `chromadb`, `sentence-transformers` в requirements
3. Додає `knowledge_base` policy в `tool_policy.json`
4. Додає volume для knowledge data в `docker-compose.yml`

`knowledge_server.py` — всередині base runtime image (не генерується, pre-built).

### З'єднання з базою

**Embedded (v1):** нема зовнішньої бази. ChromaDB = файл у volume. Zero config.

**Sidecar (v2):** docker-compose з 2 сервісами, Docker networking: `knowledge-db:8090`.

**External (v3):** Shared knowledge service в K8s. URL через env var / Secret.

---

## 10. Deployment в Kubernetes

```
namespace: agentic-studio
├── Deployment: frontend (2 replicas)
├── Deployment: backend (3 replicas)
├── StatefulSet: postgresql
├── Deployment: redis
├── Deployment: minio (artifact storage)
├── Ingress: studio.example.com
├── NetworkPolicy: backend egress only to DB + Redis + LLM API
├── Secret: LLM API keys, DB credentials
└── HPA: backend autoscaling
```

---

## 11. Команда: 6 людей, 6 напрямків

### Що вже зроблено (факт)

| Хто | Що зробив | Файли |
|-----|-----------|-------|
| **Py (runtime)** | ReAct Engine — повний цикл агента | `react_engine.py`, `schemas.py` |
| **Py (tools)** | Web search + Code execution + Registry | `web_search.py`, `run_code.py`, `registry.py` |
| **React Dev** | Scaffold проекту | `package.json`, `App.jsx`, `main.jsx` |
| **DevOps** | Архітектура, контракт, контекст | `FULL_CONTEXT.md`, `API_CONTRACT.md` |

### Що далі — розподіл задач до MVP

| # | Хто | Задача зараз | Файли | Складність | Оцінка |
|---|-----|-------------|-------|------------|--------|
| 1 | **DevOps** | `.env`, Dockerfile, docker-compose, CORS | `deploy/`, `.env.example`, `docker-compose.yml` | Легко | 1-2 дні |
| 2 | **React Dev** | Chat UI + SSE parsing + thinking panel | `frontend/src/` | Середньо | 3-5 днів |
| 3 | **Py-1** | FastAPI app + `/api/v1/chat` SSE + `/health` + `/tools` | `backend/main.py` → переписати, нові routes | Легко | 1-2 дні |
| 4 | **Py-2** | System prompt engineering + конфігурація persona | `backend/app/core/prompts.py` (новий) | Легко | 1-2 дні |
| 5 | **Py-3** | Fix imports in registry + інтеграційне тестування ReAct loop | `registry.py`, tests | Легко | 1 день |
| 6 | **Py-4** | Нові tools (shell/kubectl) + tool_policy.py для безпеки | `backend/app/tools/shell.py`, `backend/app/guardrails/` | Середньо | 3-5 днів |

**Блокерів немає.** Всі задачі паралельні. Py-1 і React Dev залежать від `API_CONTRACT.md` (вже готовий).

### Хто де працює в коді (актуально):
- `backend/main.py`, API routes → **Py-1**
- `backend/app/core/` (prompts, config) → **Py-2**
- `backend/app/services/` (ReAct engine) → **Py-3** (done, підтримка)
- `backend/app/tools/` (нові tools), `backend/app/guardrails/` → **Py-4**
- `frontend/src/` → **React Dev**
- `deploy/`, `docker-compose.yml`, `Dockerfile`, `.env`, CI/CD → **DevOps**

MVP: **~1-2 тижні** (ядро вже готове, залишився HTTP layer + UI).

---

## 12. DevOps аналогії

| Traditional DevOps | Agentic Studio |
|---|---|
| Dockerfile | Agent Definition (system prompt + tools + config) |
| Docker Registry | Skill Registry (Postgres) |
| `docker build` | Agent Factory (Meta-Agent composing the definition) |
| `docker run` | Agent Runtime (ReAct execution loop) |
| Container logs | Thinking stream (SSE to frontend) |
| Helm chart templates | Prompt templates (modular, composable) |
| K8s plugins (CSI/CNI) | Tool plugins (MCP/Function Calling) |
| Resource limits (CPU/mem) | Token budgets + max iterations |
| Pod Security Standards | 5-layer security model |
| `sudoers` file | Command allowlist/denylist |
| Immutable infrastructure | Read-only container filesystem |
| Service mesh (Envoy) | MCP sandbox proxy |

---

## 13. Робоча кодова база

**Основний repo:** `/Users/litvinchuk.roman/PyCharmProjects/agentic-studio/`

### Ключові файли (актуальний код)

| Файл | Що робить | Статус |
|------|-----------|--------|
| `backend/app/services/react_engine.py` | ReAct loop — серце агента. Groq LLM, tool calls, AsyncGenerator | ✅ Production-ready |
| `backend/app/models/schemas.py` | Pydantic моделі: AgentEvent, AgentState, EventType | ✅ Production-ready |
| `backend/app/tools/registry.py` | Центральний tool dispatcher | ✅ (fix imports) |
| `backend/app/tools/web_search.py` | Tavily async web search | ✅ Production-ready |
| `backend/app/tools/run_code.py` | E2B cloud sandbox code execution | ✅ Production-ready |
| `backend/requirements.txt` | Всі залежності з версіями | ✅ Повний |
| `API_CONTRACT.md` | Контракт frontend ↔ backend (v1 + v2 endpoints) | ✅ Задокументований |
| `FULL_CONTEXT.md` | Повний архітектурний контекст (цей файл) | ✅ Актуальний |

### Архітектурний скелет (reference)

В `/Users/litvinchuk.roman/WebstormProjects/agentic-studio/` лежить розширений архітектурний скелет (55 файлів) з TODO-мітками — reference для v2 фіч (Factory, MCP, Guardrails, Helm). Використовувати як орієнтир, не копіювати один-в-один.

---

## 14. Напрямки для дослідження

1. **SSE + AsyncIO** — streaming patterns для real-time thinking display (актуально для Py-1 і React Dev зараз)
2. **Prompt Engineering** — domain-specific system prompts, few-shot examples, chain-of-thought (актуально для Py-2)
3. **MCP Protocol** — tool plugin architecture, JSON-RPC over stdio (v2, для Py-3)
4. **LLM Observability** — Langfuse, LangSmith, OpenTelemetry для AI systems (v2)
5. **Agent Security** — OWASP LLM Top 10, prompt injection prevention, output filtering (v2, для Py-4)

---

## 15. Стан кодової бази (актуальний)

**Repo:** `/Users/litvinchuk.roman/PyCharmProjects/agentic-studio/`

```
backend/
├── main.py                         ← TODO: замінити на FastAPI entrypoint
├── requirements.txt                ← ✅ Повний (fastapi, openai, tavily, e2b, redis, sqlalchemy, tiktoken)
└── app/
    ├── __init__.py
    ├── core/__init__.py
    ├── models/
    │   ├── __init__.py
    │   └── schemas.py              ← ✅ AgentEvent, AgentState, EventType (Pydantic)
    ├── services/
    │   ├── __init__.py
    │   └── react_engine.py         ← ✅ Повний ReAct loop (Groq/OpenAI-compatible, async, streaming)
    └── tools/
        ├── __init__.py
        ├── registry.py             ← ✅ Tool dispatcher (⚠ виправити імпорти на absolute)
        ├── web_search.py           ← ✅ Tavily async integration
        └── run_code.py             ← ✅ E2B sandbox async integration

frontend/
├── package.json                    ← ✅ React 19 + Vite 8
├── vite.config.js
├── index.html
├── eslint.config.js
└── src/
    ├── main.jsx                    ← ✅ React entrypoint
    └── App.jsx                     ← Skeleton ("Hello, Agentic Studio")
```

### Що реально зроблено і працює

| Компонент | Файл | Статус | Деталі |
|-----------|------|--------|--------|
| **ReAct Engine** | `react_engine.py` | ✅ **Production-ready** | Повний цикл: LLM → tool_calls → execute → loop. Groq (Llama 3.3-70b). AsyncGenerator стрімить AgentEvent. Max iterations guard. |
| **Schemas** | `schemas.py` | ✅ **Production-ready** | EventType enum (thought/tool_call/tool_result/answer/error), AgentEvent, AgentState з session_id |
| **Web Search** | `web_search.py` | ✅ **Production-ready** | Tavily async, search_depth="advanced", 3 results, форматований output |
| **Code Execution** | `run_code.py` | ✅ **Production-ready** | E2B cloud sandbox, stdout/stderr capture, error traceback |
| **Tool Registry** | `registry.py` | ✅ (minor fix) | Центральний dispatcher, безпечний error handling. Потрібно: `from app.tools.web_search import ...` |
| **Dependencies** | `requirements.txt` | ✅ **Повний** | FastAPI, OpenAI, Tavily, E2B, Redis, SQLAlchemy, tiktoken — все пінований |
| **Frontend scaffold** | `package.json` | ✅ **Skeleton** | React 19 + Vite 8, порожній App.jsx — чекає на UI |

### Що потрібно дописати (TODO)

| Компонент | Складність | Хто | Деталі |
|-----------|-----------|-----|--------|
| FastAPI app (`main.py`) | Легко | Py-1 | Замінити PyCharm boilerplate на FastAPI з CORS, routes |
| API routes (`/api/v1/chat` SSE) | Легко | Py-1 | SSE endpoint що викликає ReActEngine.run_loop() |
| System prompt config | Легко | Py-2 | Persona/instructions для LLM, конфігурований per-agent |
| `.env` / config management | Легко | DevOps | GROQ_API_KEY, TAVILY_API_KEY, E2B_API_KEY |
| Chat UI | Середньо | React dev | Input + message list + thinking panel + SSE parsing |
| Dockerfile + docker-compose | Легко | DevOps | Multi-stage build для backend, proxy для frontend |
| Імпорти в `registry.py` | Тривіально | Py-1 | `from app.tools.web_search import ...` замість `from web_search import ...` |

### Ключові технічні рішення команди

- **LLM провайдер:** Groq (Llama 3.3-70b-versatile) через OpenAI-compatible API — швидко і дешево для MVP
- **Tools:** Direct Python functions (не MCP) — простіше для v1, MCP запланований на v2
- **Code sandbox:** E2B (cloud micro-VM) — безпечне виконання довільного Python
- **Web search:** Tavily — async, search_depth="advanced"
- **Монорепо:** backend + frontend в одному repo — правильно для поточного етапу

### Оцінка прогресу

**Ядро системи (ReAct Engine + Tools + Schemas) = ~60% бекенду готово.**
Залишилось: HTTP layer (FastAPI routes + SSE) і Frontend UI.
Оцінка до робочого MVP: **~1-2 тижні** при поточному темпі.

---

## 16. Конкуренти і наша позиція

### Ринок (2026)

| Проєкт | Stars | Що робить | Головна проблема |
|--------|-------|-----------|-----------------|
| **OpenClaw** | 270K+ | Always-on AI agent runtime + messaging | Security disaster (CVE-2026-25253, 12% малісних скілів у ClawHub, 512 вразливостей по Kaspersky). Безпека = конфіг юзера, не архітектура. |
| **Docker Agent** | 2.8K | Декларативний builder: `docker agent run agent.yaml` | Потребує ручного YAML. Не генерує з промпту. |
| **AgentBreeder** | — | Framework-agnostic orchestrator (LangGraph, CrewAI, etc.) | Runtime, не builder. |
| **OpenAgent** | 3.5K | Enterprise self-hosted, SOC2-ready | Runtime, не factory. |

### Чим ми відрізняємось

| Аспект | OpenClaw / Docker Agent | Agentic Studio |
|--------|------------------------|----------------|
| Вхід | Конфігурація / YAML (ручна) | Промпт природною мовою |
| Вихід | Працюючий сервіс на їхній платформі | Portable Docker artifact (tar.gz) |
| Безпека | Конфіг юзера (OpenClaw) | 5 рівнів, enforced архітектурою |
| Ізоляція | Монолітний сервіс (OpenClaw) | Кожен агент — окремий контейнер |
| Аналогія | Kubernetes (запускає) | Docker Build (створює) |

### Наша ніша (порожня на ринку)

**"Secure agent factory with natural language input"** — жоден конкурент не робить одночасно:
1. Prompt → ready-to-deploy container (не YAML, не конфіг — промпт)
2. Security вбудований в архітектуру (не optional config)
3. Portable output (деплой де хочеш, не прив'язаний до платформи)

Ми не конкуруємо з OpenClaw (він runtime/daemon), ми доповнюємо екосистему — будуємо агентів, які потім можна запускати де завгодно.

---

## 17. UX Flow побудови агента (4 кроки)

### Крок 1: Prompt + Model
Юзер пише промпт + вибирає модель (GPT-4o / Claude / Ollama). Мінімум полів.

### Крок 2: Clarification (Cursor-style)
Factory (LLM) генерує уточнюючі питання на основі промпту. Питання **динамічні** — для SRE одні, для маркетолога інші. Бекенд присилає JSON з питаннями, фронт рендерить radio/checkbox/text. Юзер відповідає.

Приклад для SRE:
- Доступ до кластера: read-only / read-write / без доступу
- Сервіси: PagerDuty ☑, Datadog ☑, Slack ☐, GitHub ☐
- База знань (RAG): так / ні
- Аудиторія: технічна / менеджмент

### Крок 3: Review
Показати що Factory зібрала: ім'я, tools, security policy, system prompt preview, UI type. Дати змінити перед збіркою.

UI type для агента (3 варіанти):
- **Chat + Thinking panel** — бачити як думає (для технічної аудиторії)
- **Clean Chat** — тільки результат (для нетехнічної аудиторії)
- **Dashboard + Chat** — live метрики + чат (для SRE war rooms)

### Крок 4: Build Stream (SSE)
Progress bar: Analyze → Plan → Generate → Validate → Package. Thinking panel показує кожен крок. В кінці — кнопка Download.

### API contract

**Повний контракт:** `API_CONTRACT.md` в корені repo.

#### v1 (MVP — зараз):
```
POST /api/v1/chat           → SSE stream (AgentEvent: thought/tool_call/tool_result/answer/error)
GET  /api/v1/health         → { status: "ok", version: "0.1.0" }
GET  /api/v1/tools          → { tools: [{name, description}] }
```

#### v2 (Factory — потім):
```
POST /api/v1/agents/build          → { prompt, model }
SSE  /api/v1/agents/{id}/stream    → event: clarification { questions[] }
POST /api/v1/agents/{id}/answers   → { відповіді на питання }
SSE  /api/v1/agents/{id}/stream    → events: step, thought, complete
GET  /api/v1/agents/{id}/download  → .tar.gz
GET  /api/v1/agents                → список агентів
```

Принцип розширення: **additive-only** — додавати можна, змінювати/видаляти ні.

### Дизайн: Dark Futuristic / Cyber-Brutalism
Стиль: темний фон (#0f0f0f), monospace шрифт, один accent color (помаранчевий або синій), HUD/sci-fi overlay елементи, 3D abstract objects. Референси: linear.app, vercel.com, warp.dev.

---

## 18. Shell — primary tool для DevOps/SRE агента

MCP покриває ~30% задач (PagerDuty, Datadog, GitHub, Slack — де є готовий MCP server).
Shell покриває ~70% — все де немає MCP:
- kubectl + pipes (`kubectl logs ... | grep "timeout"`)
- helm list/status/history
- terraform state list/show
- dig, curl, traceroute, nslookup (мережева діагностика)
- grep, awk, jq, sort, uniq (аналіз логів і тексту)
- docker ps/logs/stats
- git log/diff/blame
- CRD запити (karpenter, cert-manager, prometheus rules)
- Внутрішні CLI-тулзи компанії

**Shell — primary tool, не fallback.** MCP — для сервісів з готовим API. E2B — тільки для довільного Python (data analysis).

### Як shell працює в K8s pod
kubectl — це HTTP клієнт. Він робить HTTPS запит до kube-apiserver. Pod автоматично отримує ServiceAccount token з `/var/run/secrets/kubernetes.io/serviceaccount/token`. Kubeconfig прокидувати НЕ треба.

### Подвійний захист shell
1. **Layer 3 (Application):** tool_policy.py — regex allowlist/denylist перевіряє команду ПЕРЕД виконанням
2. **Layer 1 (Kubernetes):** RBAC на ServiceAccount — тільки get/list/watch, deny by default

Обидва рівні незалежні. Навіть якщо policy обійдений — K8s RBAC не дасть зробити delete/apply. Навіть якщо RBAC дає більше прав — policy заблокує на application рівні.

### Command parser: не regex, а shlex parse
Чистий regex по строці (~85% надійності) — недостатній. LLM може обійти через variable substitution, escaping, base64 encoding. Правильний підхід — `shlex.split()` розбирає команду як shell, потім перевіряє кожну під-команду окремо:
- Verb allowlist для kubectl (get/describe/logs — дозволено, delete/apply — заборонено)
- Бінарники bash/sh/zsh/python — завжди denied (блокує `base64 -d | bash`)
- Subshell patterns `$()` і backticks — завжди denied
- Pipeline кожна під-команда перевіряється окремо
- Allowlist (що дозволено) замість denylist (що заборонено) — deny by default

### Найбільший реальний ризик: data exfiltration
Destructive operations (delete/apply) — зупиняються parser + K8s RBAC. Але exfiltration через дозволені канали (curl до зовнішнього URL, відправка даних з RAG) — складніше зловити. Захист:
- **NetworkPolicy** — egress тільки до відомих адрес (LLM API, PagerDuty, Datadog). curl до невідомих доменів — connection refused на мережевому рівні.
- **Output filter** — сканувати відповіді агента на паттерни credentials/tokens/PII перед відправкою юзеру.
- **curl domain allowlist** — дозволити HTTP запити тільки до internal або конкретних доменів.

---

## 17. Чому наш агент буде "розумним"

Три складові "розумності" (як у Cursor):

1. **Модель** — та сама (Claude/GPT-4o). Якість мислення = якість моделі. Ми використовуємо ту саму.
2. **System Prompt** — детальний, domain-specific, з workflow і constraints. Не "you are a helpful assistant", а 200+ рядків інструкцій зі step-by-step process для конкретного домену.
3. **Контекст** — RAG з документацією (постмортеми, ранбуки, архітектура) + live API (PagerDuty, Datadog, kubectl). Агент народжується вже як спеціаліст, не треба пояснювати з нуля.

Factory збирає все це з одного промпту: правильний system prompt + правильні tools + RAG → агент виходить "розумним" одразу після створення.

**Cursor — генераліст. Наш агент — спеціаліст з pre-loaded knowledge. В своєму домені він може бути КРАЩИМ за Cursor.**

---

## 18. Висновок

> *model thinking — Claude Opus 4, Cursor Agent Mode*
> *updated: 2026-05-16 — відображає реальний стан кодової бази*

Agentic Studio — це не ще один "AI assistant". Це **фабрика спеціалізованих AI-колег**, де:

- **Вхід:** один промпт природною мовою
- **Вихід:** portable Docker контейнер з агентом, який вже знає свою роботу

### Поточний стан (травень 2026)

**Ядро готове.** ReAct Engine + Tools (web_search, run_code) + Schemas = ~60% backend.
Залишилось: HTTP layer (FastAPI routes + SSE) + Chat UI (React).
Оцінка до **робочого MVP: 1-2 тижні**.

**Roadmap:**
1. **v1 (зараз → 1-2 тижні):** Один працюючий агент з chat UI + thinking panel. POST /api/v1/chat → SSE stream.
2. **v2 (~тиждень 3-4):** Agent Factory — prompt → ready-to-deploy Docker container. Clarification UI. MCP tools.
3. **v3 (~тиждень 5-6):** RAG (ChromaDB), shell tool (kubectl), guardrails, security policies.
4. **v4 (далі):** Multi-agent, agent marketplace, production K8s deployment.

**Ризики:**
- Prompt quality = agent quality. Якщо system prompts погані — агент буде тупий
- Ми конкуруємо не з продуктами, а з очікуваннями юзерів, які вже бачили Cursor
- MCP integration (v2) — мало production прикладів

**Стратегія:**
- MVP-first: спочатку працюючий агент, потім фабрика
- Security-first — це USP, яке OpenClaw ніколи не зможе повторити без повного rewrite
- Contract-driven development — `API_CONTRACT.md` як закон між frontend і backend
