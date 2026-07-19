"""Lightweight token authentication.

Each person has an opaque token (see ``app.db.Person``). Clients send it in the
``X-API-Token`` header; ``get_current_user`` resolves it to a Person and is the
single isolation boundary — every conversation/message route depends on it, so
one family member can never touch another's data.

This is deliberately minimal (no passwords/JWT) for a trusted household. It
establishes a REAL boundary now; upgrading to full login later only changes how
a token is issued, not how routes enforce ownership.
"""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
from sqlmodel import Session, select

from app.db import Person, get_session


def get_current_user(
    x_api_token: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> Person:
    if not x_api_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Token header",
        )
    person = session.exec(select(Person).where(Person.token == x_api_token)).first()
    if person is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API token",
        )
    return person
