# Wiring into your existing app/main.py

Don't overwrite your existing `main.py` — just add these lines to it.

```python
from fastapi import FastAPI

from app.db.session import init_db
from app.routers import household, actions

app = FastAPI()  # <- you likely already have this line

@app.on_event("startup")
def on_startup():
    init_db()

app.include_router(household.router)
app.include_router(actions.router)
```

Then seed demo data once before your first run:

```bash
python -m app.db.seed
```

## Quick smoke test (no LLM needed yet)

```bash
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/docs` and try:

1. `GET /household/permissions` — confirm the seeded rules are there.
2. `POST /actions` with:
   ```json
   {"profile_id": "kid_1", "persona": "kid", "action_type": "weather", "params": {}}
   ```
   → should return `{"decision": "allow", "result": {...}}`
3. Same call with `"persona": "guest", "action_type": "send_email"` → should
   return `{"decision": "deny", "result": null}` (send_email integration isn't
   even wired yet, which is fine -- deny/escalate never reach `run_action`).
4. `GET /household/calendar` — confirm the audit trail lines up in your DB
   (open `household.db` with any SQLite viewer, check the `auditlog` table).

That last step (`auditlog` table populated with every decision) is the
piece worth pointing a judge at directly.
