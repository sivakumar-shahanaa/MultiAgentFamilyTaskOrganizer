"""FastAPI app: multi-user chat with per-user personas over a local LLM.

Phase 1 (persistence) + Phase 2 (users + personas) of the integration plan.
Conversations and messages are always scoped to the authenticated user via the
``get_current_user`` dependency.
"""

from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.auth import get_current_user
from app.db import Conversation, User, get_session, init_db
from app.llm import history_to_display, run_chat
from app.utils import utcnow
from app.schemas import (
    ChatMessage,
    ConversationResponse,
    CreateConversationRequest,
    CreateUserRequest,
    SendMessageRequest,
    SendMessageResponse,
    UpdateUserRequest,
    UserCreatedResponse,
    UserResponse,
)

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="MultiAgent Family Task Organizer API", lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# --- Users / personas ---------------------------------------------------------

@app.post("/users", response_model=UserCreatedResponse, status_code=status.HTTP_201_CREATED)
def create_user(request: CreateUserRequest, session: Session = Depends(get_session)) -> User:
    user = User(
        name=request.name,
        persona_prompt=request.persona_prompt,
        model=request.model,
    )
    session.add(user)
    # The unique constraint on User.name is the source of truth — relying on it
    # (rather than a prior SELECT) closes the check-then-insert race.
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Name already taken")
    session.refresh(user)
    return user  # includes token (only time it is returned)


@app.get("/users", response_model=list[UserResponse])
def list_users(session: Session = Depends(get_session)) -> list[User]:
    """Roster for the user-access-admin frontend. Tokens are never included."""
    return list(session.exec(select(User)).all())


@app.get("/users/me", response_model=UserResponse)
def get_me(user: User = Depends(get_current_user)) -> User:
    return user


@app.patch("/users/me", response_model=UserResponse)
def update_me(
    request: UpdateUserRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> User:
    """Edit the current user — notably their persona prompt."""
    data = request.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(user, key, value)
    session.add(user)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Name already taken")
    session.refresh(user)
    return user


# --- Conversations ------------------------------------------------------------

@app.post("/conversations", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
def create_conversation(
    request: CreateConversationRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ConversationResponse:
    conversation = Conversation(user_id=user.id, title=request.title)
    session.add(conversation)
    session.commit()
    session.refresh(conversation)
    return _to_conversation_response(conversation)


@app.get("/conversations", response_model=list[ConversationResponse])
def list_conversations(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[ConversationResponse]:
    rows = session.exec(select(Conversation).where(Conversation.user_id == user.id)).all()
    return [_to_conversation_response(c) for c in rows]


@app.get("/conversations/{conversation_id}/messages", response_model=list[ChatMessage])
def get_messages(
    conversation_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[ChatMessage]:
    conversation = _get_owned_conversation(conversation_id, user, session)
    return history_to_display(conversation.history_json)


@app.post("/conversations/{conversation_id}/messages", response_model=SendMessageResponse)
async def send_message(
    conversation_id: int,
    request: SendMessageRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> SendMessageResponse:
    conversation = _get_owned_conversation(conversation_id, user, session)

    reply_text, updated_history = await run_chat(
        user_id=user.id,
        user_name=user.name,
        persona_prompt=user.persona_prompt,
        model_name=user.model,
        message=request.message,
        history_json=conversation.history_json,
    )

    messages = history_to_display(updated_history)

    conversation.history_json = updated_history
    conversation.message_count = len(messages)
    conversation.updated_at = utcnow()
    session.add(conversation)
    session.commit()

    # The reply is the model's actual output, not messages[-1]: if the model
    # returns no text part, the last display message would be the user's own
    # prompt. reply_text always carries the assistant's response.
    reply = ChatMessage(role="assistant", content=reply_text)
    return SendMessageResponse(
        conversation_id=conversation_id,
        reply=reply,
        messages=messages,
    )


# --- Helpers ------------------------------------------------------------------

def _get_owned_conversation(conversation_id: int, user: User, session: Session) -> Conversation:
    conversation = session.get(Conversation, conversation_id)
    # Return 404 (not 403) for another user's thread so ownership isn't leaked.
    if conversation is None or conversation.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conversation


def _to_conversation_response(c: Conversation) -> ConversationResponse:
    return ConversationResponse(
        id=c.id,
        title=c.title,
        created_at=c.created_at,
        updated_at=c.updated_at,
        message_count=c.message_count,
    )
