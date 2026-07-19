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

## Example API usage

```bash
SESSION_ID=$(curl -s -X POST http://localhost:8000/sessions \
  -H 'content-type: application/json' \
  -d '{"system_prompt":"You are a concise household assistant."}' | jq -r .id)

curl -X POST "http://localhost:8000/sessions/$SESSION_ID/messages" \
  -H 'content-type: application/json' \
  -d '{"message":"Help me plan chores for today."}'
```

## Configuration

Set these in `.env`:

- `LOCAL_LLM_BASE_URL` defaults to `http://localhost:11434/v1`
- `LOCAL_LLM_API_KEY` defaults to `ollama`
- `LOCAL_LLM_MODEL` defaults to `llama3.2`
