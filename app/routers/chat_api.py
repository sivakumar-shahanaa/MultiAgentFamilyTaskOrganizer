"""JSON chat API for the React/blob frontend (Robyn).

The HTML chat route returns rendered pages; the avatar frontend needs the
STRUCTURED verdict so the blob can emote (allow bounce / deny shake /
escalate tilt) and render decision chips. Mirrors main.py's chat semantics:
model proposes -> gate decides -> integration runs if allowed -> everything
logged. Grounded reply text matches _final_reply_for_proposed_action, minus
the "Action ..." suffix (chips carry that in this UI).
"""
import os
import shutil
import tempfile

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from pydantic_ai.exceptions import ModelAPIError
from sqlmodel import Session, select

from app.agents import run_turn
from app.db import Person, Role, engine
from app.integrations.registry import run_action
from app.permissions.gate import check_permission, log_action
from app.personas import PERSONAS

router = APIRouter(prefix="/api", tags=["chat-api"])

# Conversation history for API clients, keyed by person id. In-memory, same
# shape run_turn expects. Separate from the HTML chat's session store.
_history: dict[str, list[dict]] = {}
_HISTORY_MAX = 12


class ChatRequest(BaseModel):
    person_id: str
    message: str = Field(min_length=1)


def _scope_for_role(role: Role) -> str:
    if role == Role.parent:
        return "parent"
    if role == Role.child:
        return "kid"
    return "guest"


def _grounded_reply(action_type: str, result, proposed_reply: str, decision: str) -> str:
    if action_type == "none":
        return proposed_reply
    if decision != "allow":
        return "I can't do that for your role."
    if action_type == "read_schedule" and isinstance(result, dict):
        events = result.get("events", [])
        if not events:
            return "You don't have anything scheduled."
        titles = ", ".join(str(e.get("title", "Untitled")) for e in events)
        return f"Your scheduled events are: {titles}."
    if action_type == "weather" and isinstance(result, dict):
        return (f"It's {result.get('condition')} and {result.get('temp_f')}°F in "
                f"{result.get('location')}. {result.get('advice')}.")
    if action_type == "spotify_play" and isinstance(result, dict):
        return f"Playing {result.get('now_playing')}."
    return proposed_reply


@router.get("/people")
def list_people() -> list[dict]:
    """Admitted people + persona display data, for the picker/chat header."""
    with Session(engine) as session:
        people = session.exec(select(Person)).all()
    out = []
    for p in people:
        persona = PERSONAS.get(p.persona.value)
        out.append({
            "id": p.id,
            "name": p.name,
            "role": p.role.value,
            "scope": _scope_for_role(p.role),
            "persona": p.persona.value,
            "display_name": persona.display_name if persona else p.persona.value,
            "accent": persona.accent if persona else "#64748b",
        })
    return out


# Lazy-loaded local Whisper (tiny, int8) — first call downloads ~75MB once at
# build time; transcription itself is fully local, zero egress at runtime.
_whisper = None


@router.post("/transcribe")
def transcribe(audio: UploadFile = File(...)) -> dict:
    """Mic input -> text via faster-whisper on this machine. Sync `def` so
    FastAPI runs it in the threadpool (whisper is CPU-blocking)."""
    global _whisper
    if _whisper is None:
        from faster_whisper import WhisperModel
        _whisper = WhisperModel("tiny", device="cpu", compute_type="int8")

    suffix = os.path.splitext(audio.filename or "clip.webm")[1] or ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        shutil.copyfileobj(audio.file, f)
        path = f.name
    try:
        segments, _info = _whisper.transcribe(path, beam_size=1)
        text = " ".join(s.text.strip() for s in segments).strip()
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"could not transcribe: {e}")
    finally:
        os.unlink(path)
    return {"text": text}


@router.post("/chat")
async def chat(req: ChatRequest) -> dict:
    with Session(engine) as session:
        person = session.get(Person, req.person_id)
    if person is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")

    history = _history.setdefault(person.id, [])
    try:
        proposed = await run_turn(person.persona.value, req.message, history)
    except ModelAPIError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Local model unreachable — is ollama running?",
        )

    decision = "allow"
    result = None
    if proposed.action != "none":
        scope = _scope_for_role(person.role)
        with Session(engine) as session:
            decision = check_permission(scope, proposed.action, session)
            result = run_action(proposed.action, proposed.params) if decision == "allow" else None
            log_action(session, person.id, proposed.action, proposed.params, decision)

    reply = _grounded_reply(proposed.action, result, proposed.reply, decision)
    history.extend([{"role": "user", "content": req.message},
                    {"role": "assistant", "content": reply}])
    del history[:-_HISTORY_MAX]

    persona = PERSONAS.get(person.persona.value)
    return {
        "person_id": person.id,
        "persona": person.persona.value,
        "accent": persona.accent if persona else "#64748b",
        "reply": reply,
        "action": proposed.action,
        "params": proposed.params,
        "decision": decision,          # "allow" | "deny" | "escalate" ("allow" for none)
        "executed": decision == "allow" and proposed.action != "none",
        "result": result,
    }
