"""Lightweight token authentication.

Each user has an opaque token (see ``app/db.User``). Clients send it in the
``X-API-Token`` header; ``get_current_user`` resolves it to a User and is the
single isolation boundary — every conversation/message route depends on it, so
one family member can never touch another's data.

This is deliberately minimal (no passwords/JWT) for a trusted household. It
establishes a REAL boundary now; upgrading to full login later only changes how
a token is issued, not how routes enforce ownership.
"""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, status
from sqlmodel import Session, select

from app.db import User, get_session


def get_current_user(
    x_api_token: str | None = Header(default=None),
    session: Session = Depends(get_session),
) -> User:
    if not x_api_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Token header",
        )
    user = session.exec(select(User).where(User.token == x_api_token)).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API token",
        )
    return user
