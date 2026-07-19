"""Repository helpers for durable chat persistence.

Thin functions over the ``Conversation``/``Message`` tables so the chat flow can
persist and reload history without touching ORM details directly.
"""

from datetime import datetime

from sqlmodel import Session, select

from app.models.conversation import Conversation, Message


def create_conversation(
    session: Session,
    *,
    profile_id: str,
    model: str | None = None,
    system_prompt: str | None = None,
) -> Conversation:
    conversation = Conversation(
        profile_id=profile_id, model=model, system_prompt=system_prompt
    )
    session.add(conversation)
    session.commit()
    session.refresh(conversation)
    return conversation


def add_message(session: Session, conversation_id: int, role: str, content: str) -> Message:
    message = Message(conversation_id=conversation_id, role=role, content=content)
    session.add(message)
    # Touch the parent conversation's updated_at so listings can sort by recency.
    conversation = session.get(Conversation, conversation_id)
    if conversation is not None:
        conversation.updated_at = datetime.utcnow()
        session.add(conversation)
    session.commit()
    session.refresh(message)
    return message


def load_messages(session: Session, conversation_id: int) -> list[Message]:
    return list(
        session.exec(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.id)
        ).all()
    )


def list_conversations(session: Session, profile_id: str) -> list[Conversation]:
    return list(
        session.exec(
            select(Conversation)
            .where(Conversation.profile_id == profile_id)
            .order_by(Conversation.updated_at.desc())
        ).all()
    )
