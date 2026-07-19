from uuid import UUID, uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, status


# Added for integrations
from app.db.session import init_db
from app.routers import household, actions
##

from app.llm import DEFAULT_MODEL, LocalChatAgent
from app.schemas import (
    ChatMessage,
    ChatSession,
    SendMessageRequest,
    SendMessageResponse,
    SessionResponse,
    StartSessionRequest,
)

load_dotenv()

app = FastAPI(title="MultiAgent Family Task Organizer API")

_sessions: dict[UUID, ChatSession] = {}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def start_session(request: StartSessionRequest) -> SessionResponse:
    session = ChatSession(
        id=uuid4(),
        model=request.model or DEFAULT_MODEL,
        system_prompt=request.system_prompt,
    )
    _sessions[session.id] = session
    return _to_session_response(session)


@app.get("/sessions/{session_id}", response_model=ChatSession)
def get_session(session_id: UUID) -> ChatSession:
    return _get_session(session_id)


@app.post("/sessions/{session_id}/messages", response_model=SendMessageResponse)
async def send_message(session_id: UUID, request: SendMessageRequest) -> SendMessageResponse:
    session = _get_session(session_id)
    agent = LocalChatAgent(session.model, session.system_prompt)

    user_message = ChatMessage(role="user", content=request.message)
    reply_text = await agent.run(request.message, session.messages)
    assistant_message = ChatMessage(role="assistant", content=reply_text)

    session.messages.extend([user_message, assistant_message])
    return SendMessageResponse(
        session_id=session.id,
        reply=assistant_message,
        messages=session.messages,
    )


def _get_session(session_id: UUID) -> ChatSession:
    session = _sessions.get(session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return session


def _to_session_response(session: ChatSession) -> SessionResponse:
    return SessionResponse(
        id=session.id,
        model=session.model,
        system_prompt=session.system_prompt,
        created_at=session.created_at,
        message_count=len(session.messages),
    )


# Added for integrations
@app.on_event("startup")
def on_startup() -> None:
    init_db()

app.include_router(household.router)
app.include_router(actions.router)
###