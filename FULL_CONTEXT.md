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

## 2. Архітектура — 3 компоненти

### Компонент 1: Frontend (React)
- Поле вводу для промпту
- SSE-стрім "thinking" — показує як фабрика думає в реальному часі
- Список збілджених агентів + кнопка Download

### Компонент 2: Backend (FastAPI — Agent Factory)
- Приймає промпт користувача
- **Orchestrator pipeline:** Analyze → Plan → Generate → Validate → Package
- LLM тільки **парсить промпт у JSON** і **генерує текст** (system prompt, persona)
- LLM **НЕ генерує код** — весь код у pre-built шаблонах
- Результат: tar.gz архів або Docker image

### Компонент 3: Base Runtime Image (Docker image)
- Двигун всередині кожного згенерованого агента
- Містить: FastAPI сервер, ReAct loop, MCP client, guardrails, frontend (3 статичних файли)
- Кожен агент = тільки конфіг, накладений на base image
- Оновлюється централізовано — виправив баг один раз, всі агенти отримають фікс

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

---

## 3. Ключове рішення: LLM генерує конфіг, НЕ код

| Що робить LLM (5-10 сек) | Що роблять шаблони (<1 сек) |
|---------------------------|----------------------------|
| Парсить промпт → JSON | Рендерить Dockerfile |
| Вибирає інструменти | Збирає requirements |
| Генерує system prompt (текст) | Копіює tool modules |
| Генерує persona (текст) | Компонує docker-compose.yml |

Чому НЕ генеруємо код: повільно (2-5 хв), ненадійно (~60-70%), небезпечно, неможливо підтримувати.
Hybrid підхід: збірка за ~10-15 сек, надійність ~98%+.

---

## 4. MCP (Model Context Protocol) — інструменти

Стандартний протокол підключення інструментів до LLM. Як USB для AI.

Кожен інструмент = MCP сервер (subprocess):
- `@tavily/mcp-server` — пошук в інтернеті
- `@anthropic/mcp-browser` — навігація по веб-сторінках
- `@modelcontextprotocol/server-filesystem` — файли
- `@modelcontextprotocol/server-github` — GitHub API
- `@modelcontextprotocol/server-slack` — Slack

Як працює:
1. Runtime читає `mcp_servers.json`
2. Запускає кожен MCP сервер як subprocess (stdio transport)
3. Викликає `tools/list` — дізнається доступні інструменти
4. Передає список LLM
5. LLM вирішує що викликати → Runtime маршрутизує

---

## 5. ReAct Loop — як агент думає

```
while not done:
    1. Відправити (system_prompt + історія + інструменти) → LLM
    2. LLM відповідає:
       a. Фінальна відповідь → повернути користувачу, done
       b. Виклик інструменту → виконати, додати результат в історію, loop
    3. Стрімити кожен крок на фронтенд через SSE
```

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

## 8. Два репозиторії

### Repo 1: `agentic-studio` (платформа)
```
├── backend/              ← Agent Factory (FastAPI)
│   └── app/
│       ├── api/          ← routes, schemas
│       ├── core/         ← config, database, models
│       ├── factory/      ← orchestrator, analyzer, planner, generator, validator, packager
│       └── templates/    ← prompts/, tools/, policies/
├── frontend/             ← Studio UI (React)
└── deploy/helm/          ← Kubernetes deployment
```

### Repo 2: `agentic-runtime` (base image для агентів)
```
├── Dockerfile
├── runtime/
│   ├── main.py           ← FastAPI що працює всередині кожного агента
│   ├── loop/react.py     ← ReAct loop
│   ├── llm/client.py     ← OpenAI/Anthropic client
│   ├── mcp/manager.py    ← MCP subprocess manager
│   ├── guardrails/       ← budget.py, tool_policy.py
│   └── api/routes.py     ← /chat (SSE), /health
├── frontend/             ← default agent UI (HTML/JS/CSS)
└── tools/                ← knowledge_server.py (RAG MCP)
```

**Чому 2 repo:**
- Різний lifecycle: runtime має semver (1.0.0, 1.0.1), backend — просто deploy
- Різні споживачі: runtime використовують агенти (зовнішні), backend — тільки ви
- Breaking changes: старі агенти на 1.x продовжують працювати коли вийде 2.0
- Security boundary: runtime працює у клієнта, backend — у вас

На старті можна монорепо. Розділяти коли runtime отримає перший semver tag (~тиждень 3-4).

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

| # | Хто | Напрямок | Що робить | Складність |
|---|-----|----------|-----------|------------|
| 1 | **DevOps** | Infra & Platform | CI/CD, docker-compose, Dockerfile, Helm, NetworkPolicy, base image pipeline | Mid-Senior |
| 2 | **React Dev** | Studio Frontend | React UI: prompt input, SSE thinking viewer, agent list, download | Mid |
| 3 | **Py-1** | Backend API + Factory | FastAPI routes, orchestrator, DB, packaging | Mid |
| 4 | **Py-2** | LLM Integration | OpenAI/Anthropic client, intent analyzer (prompt→JSON), prompt engineering | Mid |
| 5 | **Py-3** | Agent Runtime Engine | ReAct loop, MCP manager, LLM client, SSE streaming | **Senior** |
| 6 | **Py-4** | Security & Guardrails | Tool policy engine, command filtering, budget limits, MCP sandbox, audit | **Senior** |

**Всі 6 стартують з Day 1 — без блокерів.** Py-3 і Py-4 повністю незалежні.
MVP: ~6 тижнів.

### Хто де працює в коді:
- `backend/app/api/`, `core/`, `factory/` (крім analyzer) → **Py-1**
- `backend/app/factory/analyzer.py`, `templates/prompts/` → **Py-2**
- `runtime/runtime/` (loop, llm, mcp, api) → **Py-3**
- `runtime/runtime/guardrails/`, `templates/policies/` → **Py-4**
- `frontend/` → **React Dev**
- `deploy/`, `docker-compose.yml`, `Dockerfile`-s, CI/CD → **DevOps**

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

## 13. Готовий код-скелет

Повний працюючий скелет з TODO-мітками лежить у:
**`/Users/litvinchuk.roman/WebstormProjects/agentic-studio/`** (55 файлів)
**`/Users/litvinchuk.roman/WebstormProjects/agent-example/`** (8 файлів — приклад згенерованого агента)

Ключові файли:
- `PRESENTATION.md` — 5-хвилинна презентація для команди
- `TEAM_PLAN.md` — ролі, відповідальності, план по тижнях для кожного
- `backend/app/factory/orchestrator.py` — серце Agent Factory (pipeline з SSE)
- `runtime/runtime/loop/react.py` — ReAct loop (двигун агента)
- `runtime/runtime/guardrails/tool_policy.py` — policy engine
- `deploy/helm/` — Helm chart для K8s

---

## 14. Напрямки для дослідження

1. **LangGraph / CrewAI** — production agent frameworks, state machines для LLM reasoning
2. **SSE + AsyncIO** — streaming patterns для real-time thinking display
3. **Prompt Engineering** — dynamic prompt composition з модульних fragments
4. **MCP Protocol** — tool plugin architecture, JSON-RPC over stdio
5. **LLM Observability** — Langfuse, LangSmith, OpenTelemetry для AI systems

---

## 15. Стан PyCharm repo

`/Users/litvinchuk.roman/PyCharmProjects/agentic-studio/` — розробники створили порожній скелет:

```
backend/
├── main.py               ← PyCharm шаблон (Hello World)
└── app/
    ├── __init__.py        ← порожній
    ├── core/__init__.py   ← порожній
    ├── models/__init__.py ← порожній
    ├── services/__init__.py ← порожній
    └── tools/__init__.py  ← порожній
```

Структура пакетів логічна, але відрізняється від нашої архітектури:
- `services/` → треба `factory/` (pipeline: orchestrator→analyzer→planner→generator→validator→packager)
- `tools/` → треба `templates/tools/` (MCP конфіг-шаблони, не Python код)
- Немає `api/` (routes, schemas)
- Немає `runtime/` (base image — окрема репо)
- Немає `frontend/`

**Рекомендація:** перенести готовий скелет з WebstormProjects — там вже є 55 файлів з TODO-мітками.

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
```
POST /agents/build          → { prompt, model }
SSE  /agents/{id}/stream    → event: clarification { questions[] }
POST /agents/{id}/answers   → { відповіді на питання }
SSE  /agents/{id}/stream    → events: step, thought, complete
GET  /agents/{id}/download  → .tar.gz
```

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

Agentic Studio — це не ще один "AI assistant". Це **фабрика спеціалізованих AI-колег**, де:

- **Вхід:** один промпт природною мовою
- **Вихід:** portable Docker контейнер з агентом, який вже знає свою роботу

**Чому це має сенс:**
- Ніша порожня — ніхто не робить "prompt → secure deployable agent"
- OpenClaw — security disaster, монолітний runtime, не builder
- Docker Agent — потребує ручного YAML, нема auto-generation з промпту
- Ми єдині хто поєднує: NL input + security by architecture + portable output + pre-loaded domain knowledge

**Чому це реально для команди з 6 людей за 6 тижнів:**
- LLM генерує тільки конфіг і текст, не код → надійно, швидко
- Base runtime image — одна кодова база для всіх агентів → maintainable
- Кожен stream незалежний → паралельна робота з Day 1
- Модель (Claude/GPT-4o) — вже існує і "розумна". Ми будуємо правильну обгортку навколо неї

**Ризики:**
- MCP protocol integration (Py-3) — найскладніша частина, мало документації
- Prompt quality = agent quality. Якщо prompt templates погані — агенти будуть тупі
- Ми конкуруємо не з продуктами, а з очікуваннями юзерів, які вже бачили Cursor

**Стратегія:**
- MVP: SRE agent + Marketing agent (два домени, proof of concept)
- Потім: розширення template registry (нові домени, нові tools)
- Security-first — це USP, яке OpenClaw ніколи не зможе повторити без повного rewrite
