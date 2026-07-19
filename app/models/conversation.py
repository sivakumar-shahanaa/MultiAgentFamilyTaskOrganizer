"""Durable chat persistence.

The chat flow in ``app/main.py`` currently keeps sessions in an in-memory dict
(``_sessions``), so history is lost on restart. These tables provide a
DB-backed store for the same shape (a session + its messages), keyed to a
``Profile``, ready to replace the in-memory store when the chat flow is wired
to the database. Not yet referenced by ``main.py`` — see ``MAIN_WIRING.md``.

Helpers to create/append/load live in ``app/db/conversations.py``.
"""

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Conversation(SQLModel, table=True):
    """One chat thread belonging to a household member."""

    id: Optional[int] = Field(default=None, primary_key=True)
    profile_id: str = Field(foreign_key="profile.id", index=True)
    model: Optional[str] = None
    system_prompt: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Message(SQLModel, table=True):
    """A single turn within a conversation, in send order."""

    id: Optional[int] = Field(default=None, primary_key=True)
    conversation_id: int = Field(foreign_key="conversation.id", index=True)
    role: str                                   # "user" | "assistant"
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
