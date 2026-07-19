"""Identity and conversation database models."""

from __future__ import annotations

import os
import secrets
import time
from datetime import datetime
from enum import Enum
from typing import Iterator

from dotenv import load_dotenv
from sqlmodel import Field, Session, SQLModel, create_engine

from app.utils import utcnow

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")
_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args)


class Role(str, Enum):
    parent = "Parent"
    child = "Child"
    guest = "Guest"


class AccessStatus(str, Enum):
    pending = "Pending"
    accepted = "Accepted"


class PersonaKey(str, Enum):
    chris = "chris"
    julie = "julie"
    spencer = "spencer"
    marta = "marta"
    guest = "guest"


def _new_token() -> str:
    return secrets.token_urlsafe(24)


def _new_ulid() -> str:
    alphabet = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
    value = (int(time.time() * 1000) << 80) | secrets.randbits(80)
    chars = []
    for _ in range(26):
        chars.append(alphabet[value & 31])
        value >>= 5
    return "".join(reversed(chars))


class Person(SQLModel, table=True):
    id: str = Field(default_factory=_new_ulid, primary_key=True)
    name: str = Field(index=True, unique=True)
    role: Role = Field(default=Role.guest, index=True)
    persona: PersonaKey = Field(default=PersonaKey.guest, index=True)
    token: str = Field(default_factory=_new_token, index=True, unique=True)
    model: str | None = None
    created_at: datetime = Field(default_factory=utcnow)


class AccessRequest(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    status: AccessStatus = Field(default=AccessStatus.pending, index=True)
    person_id: str | None = Field(default=None, foreign_key="person.id")


class Conversation(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    person_id: str = Field(foreign_key="person.id", index=True)
    title: str | None = None
    history_json: str = Field(default="[]")
    message_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


# Backward-compatible name while routes/tests migrate from Peter's User model.
User = Person


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
