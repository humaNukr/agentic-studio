# Backend Starter

Minimal Core API and database starter for the Agentic Studio hackathon.

It is intentionally not a full SaaS app. It only demonstrates the first working backend flow:

- create an agent config
- list saved agents
- create an API key for an agent
- call `/chat` with `X-API-Key`
- download a generated config zip

## Run

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

The default DB is local SQLite at `./agentic_studio.db`.

## Try It

```bash
curl -X POST http://localhost:8000/agents \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "Marketing Agent",
    "description": "Researches trends",
    "system_prompt": "You are a marketing research agent.",
    "tools": ["web_search"],
    "tool_policy": {"max_tool_calls": 5}
  }'
```

```bash
curl -X POST http://localhost:8000/agents/1/api-keys \
  -H 'Content-Type: application/json' \
  -d '{"name": "demo"}'
```

```bash
curl -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: <key from previous response>' \
  -d '{"message": "hello"}'
```

```bash
curl -L http://localhost:8000/agents/1/download -o agent.zip
```
