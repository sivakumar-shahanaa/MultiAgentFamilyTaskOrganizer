"""Database models and session management.

Phase 1 of the multi-user integration: persistence replaces the in-memory
``_sessions`` dict. SQLite keeps infra at zero for household scale; the models
are written so a later move to Postgres + pgvector (for RAG) is mechanical.

Design note: a Conversation stores the Pydantic AI message history natively as
serialized JSON (``history_json``) rather than a separate Message table. This is
the single source of truth for a conversation, round-trips tool calls once
Phase 3 lands, and avoids drift between "what we show" and "what we send the
model". Display messages are derived from it in ``app/llm.py``.
"""

from __future__ import annotations

import os
import secrets
from datetime import datetime
from typing import Iterator

from dotenv import load_dotenv
from sqlmodel import Field, Session, SQLModel, create_engine

from app.utils import utcnow

# Load .env before reading config: this module is imported (via app.auth) before
# main.py's own load_dotenv() runs, so without this DATABASE_URL from .env would
# be missed and the default used silently.
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")

# check_same_thread=False lets the SQLite connection be shared across the
# threadpool FastAPI uses for sync work. Safe for our access patterns.
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args)


def _new_token() -> str:
    return secrets.token_urlsafe(24)


class User(SQLModel, table=True):
    """A person in the household with their own personal agent.

    Phase 2: persona lives here (one agent per user for now). ``token`` is the
    lightweight auth credential — presented via the ``X-API-Token`` header to
    resolve the caller's identity, which is the isolation boundary for
    conversations and (later) long-term memory.
    """

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    token: str = Field(default_factory=_new_token, index=True, unique=True)
    # The user-authored persona prompt. Layered UNDER a fixed base prompt at
    # run time (see app/llm.py) so it can shape voice/behavior without being
    # able to override tool-use or safety instructions.
    persona_prompt: str | None = None
    # Optional per-user model override; falls back to the configured default.
    model: str | None = None
    created_at: datetime = Field(default_factory=utcnow)


class Conversation(SQLModel, table=True):
    """One chat thread belonging to a single user.

    ``history_json`` holds the serialized Pydantic AI message list. Ownership is
    enforced everywhere by matching ``user_id`` against the authenticated user.
    """

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    title: str | None = None
    history_json: str = Field(default="[]")
    # Denormalized count of display messages, maintained on write, so listing
    # conversations doesn't have to deserialize every thread's full history.
    message_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
