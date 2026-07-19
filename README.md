# MultiAgentFamilyTaskOrganizer

An on-device AI that runs several parallel conversations from a single small local model, each scoped to a different person in the household.

## Scaffold

FastAPI API with Pydantic AI for chat sessions backed by a local OpenAI-compatible LLM endpoint, such as Ollama.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env

# In another terminal, start your local model server, for example:
ollama serve
ollama pull llama3.2

uvicorn app.main:app --reload
```

API docs: <http://localhost:8000/docs>

## Multi-user model

Each household member is a `User` with their own **persona prompt** (which shapes
their personal agent's voice/behavior) and their own conversations. Requests are
authenticated with the user's opaque token via the `X-API-Token` header — this is
the isolation boundary, so no one can read another member's threads.

State is persisted in SQLite (via SQLModel); conversation history is stored in
Pydantic AI's native format so it round-trips cleanly.

## Example API usage

```bash
# 1. Create a user with a persona. The response includes a one-time token.
TOKEN=$(curl -s -X POST http://localhost:8000/users \
  -H 'content-type: application/json' \
  -d '{"name":"Alex","persona_prompt":"Be a terse, upbeat coach. Never use emoji."}' \
  | jq -r .token)

# 2. Start a conversation (scoped to this user via the token).
CONV_ID=$(curl -s -X POST http://localhost:8000/conversations \
  -H "X-API-Token: $TOKEN" -H 'content-type: application/json' \
  -d '{"title":"Today"}' | jq -r .id)

# 3. Chat.
curl -X POST "http://localhost:8000/conversations/$CONV_ID/messages" \
  -H "X-API-Token: $TOKEN" -H 'content-type: application/json' \
  -d '{"message":"Help me plan chores for today."}'

# Update the persona any time:
curl -X PATCH http://localhost:8000/users/me \
  -H "X-API-Token: $TOKEN" -H 'content-type: application/json' \
  -d '{"persona_prompt":"Be warm and detailed."}'
```

## Configuration

Set these in `.env`:

- `LOCAL_LLM_BASE_URL` defaults to `http://localhost:11434/v1`
- `LOCAL_LLM_API_KEY` defaults to `ollama`
- `LOCAL_LLM_MODEL` defaults to `llama3.2`
- `DATABASE_URL` defaults to `sqlite:///./app.db`
