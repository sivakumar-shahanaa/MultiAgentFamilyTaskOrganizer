from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db.session import get_session
from app.models import CalendarEvent, Presence, PermissionRule

router = APIRouter(prefix="/household", tags=["household"])


# ---- Calendar ----

class CalendarEventCreate(BaseModel):
    title: str
    start_time: datetime
    end_time: datetime
    owner_id: str
    visible_to: str = "household"


@router.get("/calendar")
def list_calendar(session: Session = Depends(get_session)):
    return session.exec(select(CalendarEvent)).all()


@router.post("/calendar")
def create_calendar_event(body: CalendarEventCreate, session: Session = Depends(get_session)):
    event = CalendarEvent(**body.dict())
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


# ---- Presence ----

class PresenceUpdate(BaseModel):
    profile_id: str
    location: str


@router.get("/presence")
def list_presence(session: Session = Depends(get_session)):
    return session.exec(select(Presence)).all()


@router.post("/presence")
def update_presence(body: PresenceUpdate, session: Session = Depends(get_session)):
    existing = session.get(Presence, body.profile_id)
    if existing:
        existing.location = body.location
        existing.updated_at = datetime.utcnow()
        session.add(existing)
    else:
        existing = Presence(
            profile_id=body.profile_id,
            location=body.location,
            updated_at=datetime.utcnow(),
        )
        session.add(existing)
    session.commit()
    session.refresh(existing)
    return existing


# ---- Permission table ----

class PermissionRuleUpdate(BaseModel):
    decision: str  # "allow" | "deny" | "escalate"


@router.get("/permissions")
def list_permissions(session: Session = Depends(get_session)):
    return session.exec(select(PermissionRule)).all()


@router.patch("/permissions/{rule_id}")
def update_permission(
    rule_id: int, body: PermissionRuleUpdate, session: Session = Depends(get_session)
):
    # NOTE: stubbed open for now. In production this endpoint should be
    # gated to "parent" persona only, enforced the same way actions are.
    rule = session.get(PermissionRule, rule_id)
    if not rule:
        return {"status": "not_found"}
    rule.decision = body.decision
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule
