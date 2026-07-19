"""API request/response models (DTOs), kept separate from the DB models."""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.db import PersonaKey, Role


# --- Users / personas ---------------------------------------------------------

class CreateUserRequest(BaseModel):
    name: str = Field(min_length=1, description="Household member's name (unique).")
    role: Optional[Role] = Field(default=None, description="Permission scope.")
    persona: Optional[PersonaKey] = Field(default=None, description="Agent voice/persona.")
    model: Optional[str] = Field(
        default=None, description="Optional per-user model override, e.g. llama3.2"
    )


class UpdateUserRequest(BaseModel):
    """All fields optional — a partial update."""

    name: Optional[str] = Field(default=None, min_length=1)
    role: Optional[Role] = None
    persona: Optional[PersonaKey] = None
    model: Optional[str] = None


class UserResponse(BaseModel):
    id: str
    name: str
    role: Role
    persona: PersonaKey
    model: Optional[str]
    created_at: datetime


class UserCreatedResponse(UserResponse):
    """Returned once on creation — includes the token the client must store."""

    token: str


# --- Conversations / messages -------------------------------------------------


class StartSessionRequest(BaseModel):
    model: str | None = Field(default=None, description="Local model name, e.g. llama3.2")
    system_prompt: str | None = Field(
        default=None,
        description="Optional instructions for this chat session.",
    )


class ChatMessage(BaseModel):
    role: str
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CreateConversationRequest(BaseModel):
    title: Optional[str] = Field(default=None, description="Optional thread title.")


class ConversationResponse(BaseModel):
    id: int
    title: Optional[str]
    created_at: datetime
    updated_at: datetime
    message_count: int


class SendMessageRequest(BaseModel):
    message: str = Field(min_length=1)


class ChatSession(BaseModel):
    id: UUID
    model: str
    system_prompt: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    messages: list[ChatMessage] = Field(default_factory=list)


class SessionResponse(BaseModel):
    id: UUID
    model: str
    system_prompt: str | None
    created_at: datetime
    message_count: int


class SendMessageResponse(BaseModel):
    conversation_id: int | None = None
    session_id: UUID | None = None
    reply: ChatMessage
    messages: list[ChatMessage]
