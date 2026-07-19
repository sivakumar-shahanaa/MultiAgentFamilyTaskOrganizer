"""Tests for the durable Conversation/Message persistence layer.

Uses a throwaway SQLite engine per test so nothing touches household.db.
"""

import pathlib
import tempfile

from sqlmodel import Session, SQLModel, create_engine

from app.db.conversations import (
    add_message,
    create_conversation,
    list_conversations,
    load_messages,
)
from app.models import Conversation, Message, Profile  # noqa: F401 (registers tables)


def _fresh_engine():
    tmp = tempfile.mkdtemp(prefix="conv_test_")
    url = f"sqlite:///{pathlib.Path(tmp, 't.db').as_posix()}"
    engine = create_engine(url, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return engine


def _add_profile(session, pid="parent_1"):
    session.add(Profile(id=pid, persona="parent", display_name="Chris"))
    session.commit()


def test_create_add_and_load_in_order():
    with Session(_fresh_engine()) as s:
        _add_profile(s)
        conv = create_conversation(s, profile_id="parent_1", model="llama3.2",
                                   system_prompt="Be helpful.")
        assert conv.id is not None
        add_message(s, conv.id, "user", "hello")
        add_message(s, conv.id, "assistant", "hi there")

        msgs = load_messages(s, conv.id)
        assert [(m.role, m.content) for m in msgs] == [
            ("user", "hello"), ("assistant", "hi there")
        ]


def test_conversations_are_scoped_to_profile():
    with Session(_fresh_engine()) as s:
        _add_profile(s, "parent_1")
        _add_profile(s, "kid_1")
        c_parent = create_conversation(s, profile_id="parent_1")
        c_kid = create_conversation(s, profile_id="kid_1")

        assert [c.id for c in list_conversations(s, "parent_1")] == [c_parent.id]
        assert [c.id for c in list_conversations(s, "kid_1")] == [c_kid.id]


def test_history_survives_a_new_session():
    engine = _fresh_engine()
    with Session(engine) as s:
        _add_profile(s)
        conv = create_conversation(s, profile_id="parent_1")
        add_message(s, conv.id, "user", "remember me")
        conv_id = conv.id

    # Different Session, same DB: this is the whole point vs the in-memory dict.
    with Session(engine) as s2:
        msgs = load_messages(s2, conv_id)
        assert len(msgs) == 1
        assert msgs[0].content == "remember me"
