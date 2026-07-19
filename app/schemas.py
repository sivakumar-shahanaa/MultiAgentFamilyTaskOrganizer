from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, Field


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


class SendMessageRequest(BaseModel):
    message: str = Field(min_length=1)


class SendMessageResponse(BaseModel):
    session_id: UUID
    reply: ChatMessage
    messages: list[ChatMessage]
