"""User/persona conversation database models for token-auth chat APIs."""

from __future__ import annotations

import os
import secrets
from datetime import datetime
from typing import Iterator

from dotenv import load_dotenv
from sqlmodel import Field, Session, SQLModel, create_engine

from app.utils import utcnow

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args)


def _new_token() -> str:
    return secrets.token_urlsafe(24)


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    token: str = Field(default_factory=_new_token, index=True, unique=True)
    persona_prompt: str | None = None
    model: str | None = None
    created_at: datetime = Field(default_factory=utcnow)


class Conversation(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    title: str | None = None
    history_json: str = Field(default="[]")
    message_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
