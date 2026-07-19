"""JSON chat API for the React/blob frontend (Robyn).

The HTML chat route returns rendered pages; the avatar frontend needs the
STRUCTURED verdict so the blob can emote (allow bounce / deny shake /
escalate tilt) and render decision chips.

Adapted to the capabilities architecture: the agent calls household tools
itself (permission check + execution + audit happen inside the tools, see
app/capabilities.py). We run the agent with our own AgentDeps and read the
recorded CapabilityResult to surface {action, decision, executed} to the UI.
"""
import os
import shutil
import tempfile

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from pydantic_ai.exceptions import ModelAPIError
from sqlmodel import Session, select

from app.agents import AgentDeps, make_agent
from app.db import Person, Role, engine
from app.personas import PERSONAS

router = APIRouter(prefix="/api", tags=["chat-api"])

# Conversation history for API clients, keyed by person id. In-memory, same
# [{role, content}] shape the agents expect. Separate from the HTML chat.
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
# build time; transcription itself is fully local.
_whisper = None


@router.post("/transcribe")
def transcribe(audio: UploadFile = File(...)) -> dict:
    """Mic input -> text via faster-whisper on this machine. Sync `def` so
    FastAPI runs it in the threadpool (whisper is CPU-blocking)."""
    global _whisper
    if _whisper is None:
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Voice transcription requires faster-whisper to be installed.",
            )
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
    prompt = req.message
    if history:
        transcript = "\n".join(f"{m['role']}: {m['content']}" for m in history)
        prompt = f"Conversation so far:\n{transcript}\n\nuser: {req.message}"

    agent = make_agent(person.persona.value)
    deps = AgentDeps(person=person)
    try:
        result = await agent.run(prompt, deps=deps)
    except ModelAPIError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Local model unreachable — is ollama running?",
        )

    # Prefer the capability's grounded message (same behavior as run_turn).
    cap = deps.last_capability_result
    if deps.last_capability_message is not None:
        reply = deps.last_capability_message
    else:
        reply = str(result.output if hasattr(result, "output") else result.data)

    history.extend([{"role": "user", "content": req.message},
                    {"role": "assistant", "content": reply}])
    del history[:-_HISTORY_MAX]

    persona = PERSONAS.get(person.persona.value)
    return {
        "person_id": person.id,
        "persona": person.persona.value,
        "accent": persona.accent if persona else "#64748b",
        "reply": reply,
        "action": cap.action_type if cap else "none",
        "params": {},
        "decision": cap.decision if cap else "allow",   # "allow" for pure chat
        "executed": bool(cap and cap.decision == "allow"),
        "result": cap.result if cap else None,
    }
