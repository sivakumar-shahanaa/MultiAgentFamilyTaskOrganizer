"""Typed capabilities used by chat agents.

These are deliberately normal Python functions with Pydantic-validated inputs.
They are the execution boundary between an agent's proposed intent and Sahana's
integrations/permission/audit system. The functions are also shaped so they can
be registered as Pydantic AI tools without changing their internals.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Literal

from pydantic import BaseModel, Field
from sqlmodel import Session

from app.db import Person, Role
from app.db.session import engine
from app.integrations.registry import run_action
from app.permissions.gate import check_permission, log_action


class CapabilityResult(BaseModel):
    action_type: str
    decision: Literal["allow", "deny", "escalate"]
    result: dict | None = None


class WeatherParams(BaseModel):
    location: str = "home"


class SpotifyParams(BaseModel):
    track: str = "Unknown"


class ReadScheduleParams(BaseModel):
    pass


class WriteScheduleParams(BaseModel):
    title: str = "Scheduled event"
    start_time: datetime | None = None
    end_time: datetime | None = None
    date: str | None = None
    day: str | None = None
    time: str | None = None
    visible_to: str = "household"


def execute_capability(person: Person, action_type: str, params: dict) -> CapabilityResult:
    """Validate, permission-check, execute, and audit one proposed action."""
    if action_type == "none":
        return CapabilityResult(action_type=action_type, decision="allow", result=None)

    normalized_params = _normalize_params(person, action_type, params)
    permission_scope = _permission_scope_for_role(person.role)

    with Session(engine) as session:
        decision = check_permission(permission_scope, action_type, session)
        result = run_action(action_type, normalized_params) if decision == "allow" else None
        log_action(session, person.id, action_type, normalized_params, decision)

    return CapabilityResult(action_type=action_type, decision=decision, result=result)


def _normalize_params(person: Person, action_type: str, params: dict) -> dict:
    if action_type == "weather":
        return WeatherParams.model_validate(params).model_dump()
    if action_type == "spotify_play":
        return SpotifyParams.model_validate(params).model_dump()
    if action_type == "read_schedule":
        return ReadScheduleParams.model_validate(params).model_dump()
    if action_type == "write_schedule":
        schedule = WriteScheduleParams.model_validate(params)
        start_time = schedule.start_time or _parse_schedule_start(schedule)
        if start_time is None:
            return {"action": "error", "message": "missing start_time or understandable day/time"}
        end_time = schedule.end_time or start_time + timedelta(hours=1)
        return {
            "action": "create",
            "title": schedule.title,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "owner_id": person.id,
            "visible_to": schedule.visible_to,
        }
    return params


def _parse_schedule_start(schedule: WriteScheduleParams) -> datetime | None:
    parsed_time = _parse_time(schedule.time or "09:00")
    if parsed_time is None:
        return None
    hour, minute = parsed_time

    if schedule.date:
        try:
            base_date = datetime.fromisoformat(schedule.date).date()
        except ValueError:
            return None
    elif schedule.day:
        target_weekday = _WEEKDAYS.get(schedule.day.strip().lower())
        if target_weekday is None:
            return None
        today = datetime.now().date()
        days_ahead = (target_weekday - today.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        base_date = today + timedelta(days=days_ahead)
    else:
        return None

    return datetime.combine(base_date, datetime.min.time()).replace(hour=hour, minute=minute)


def _parse_time(time_text: str) -> tuple[int, int] | None:
    text = time_text.strip().lower().replace(" ", "")
    match = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?(am|pm)?", text)
    if match is None:
        return None

    hour = int(match.group(1))
    minute = int(match.group(2) or "0")
    meridiem = match.group(3)

    if minute > 59:
        return None
    if meridiem:
        if hour < 1 or hour > 12:
            return None
        if meridiem == "pm" and hour != 12:
            hour += 12
        if meridiem == "am" and hour == 12:
            hour = 0
    elif hour > 23:
        return None

    return hour, minute


def _permission_scope_for_role(role: Role) -> str:
    if role == Role.parent:
        return "parent"
    if role == Role.child:
        return "kid"
    return "guest"


_WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}
