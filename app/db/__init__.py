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
    _ensure_identity_schema()


def _ensure_identity_schema() -> None:
    """Small SQLite-only migration for prototype DBs created before Person grew.

    This is non-destructive: it only adds missing nullable/defaulted columns.
    """
    if not DATABASE_URL.startswith("sqlite"):
        return

    with engine.begin() as connection:
        tables = {
            row[0]
            for row in connection.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if "person" in tables:
            columns = {
                row[1]
                for row in connection.exec_driver_sql("PRAGMA table_info(person)").fetchall()
            }
            if "persona" not in columns:
                connection.exec_driver_sql(
                    "ALTER TABLE person ADD COLUMN persona VARCHAR NOT NULL DEFAULT 'guest'"
                )
            if "token" not in columns:
                connection.exec_driver_sql("ALTER TABLE person ADD COLUMN token VARCHAR")
                rows = connection.exec_driver_sql("SELECT id FROM person WHERE token IS NULL").fetchall()
                for row in rows:
                    connection.exec_driver_sql(
                        "UPDATE person SET token = ? WHERE id = ?",
                        (_new_token(), row[0]),
                    )
            if "model" not in columns:
                connection.exec_driver_sql("ALTER TABLE person ADD COLUMN model VARCHAR")
            if "created_at" not in columns:
                connection.exec_driver_sql("ALTER TABLE person ADD COLUMN created_at DATETIME")
                connection.exec_driver_sql(
                    "UPDATE person SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"
                )

        if "conversation" in tables:
            columns = {
                row[1]
                for row in connection.exec_driver_sql("PRAGMA table_info(conversation)").fetchall()
            }
            if "person_id" not in columns and "user_id" in columns:
                connection.exec_driver_sql("ALTER TABLE conversation ADD COLUMN person_id VARCHAR")
                connection.exec_driver_sql("UPDATE conversation SET person_id = CAST(user_id AS TEXT)")

        if "spotifycredential" in tables:
            columns = {
                row[1]
                for row in connection.exec_driver_sql("PRAGMA table_info(spotifycredential)").fetchall()
            }
            if "account_id" not in columns and "person_id" in columns:
                connection.exec_driver_sql(
                    """
                    CREATE TABLE spotifycredential_new (
                        account_id VARCHAR NOT NULL PRIMARY KEY,
                        access_token VARCHAR NOT NULL,
                        refresh_token VARCHAR NOT NULL,
                        expires_at DATETIME NOT NULL
                    )
                    """
                )
                existing = connection.exec_driver_sql(
                    "SELECT access_token, refresh_token, expires_at FROM spotifycredential LIMIT 1"
                ).fetchone()
                if existing is not None:
                    connection.exec_driver_sql(
                        """
                        INSERT INTO spotifycredential_new
                            (account_id, access_token, refresh_token, expires_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        ("household", existing[0], existing[1], existing[2]),
                    )
                connection.exec_driver_sql("DROP TABLE spotifycredential")
                connection.exec_driver_sql("ALTER TABLE spotifycredential_new RENAME TO spotifycredential")


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
