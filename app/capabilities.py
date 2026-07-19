"""Typed household capabilities for Pydantic AI agents."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel
from pydantic_ai import RunContext
from pydantic_ai.capabilities import Capability
from sqlmodel import Session

from app.db import Person, Role
from app.db.session import engine
from app.integrations.registry import run_action
from app.permissions.gate import check_permission, log_action


class CapabilityResult(BaseModel):
    action_type: str
    decision: Literal["allow", "deny", "escalate"]
    result: dict | None = None
    message: str


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


def household_capability() -> Capability[Any]:
    """Custom capability grouping all household action tools."""
    return Capability(
        id="household_capabilities",
        description="Weather, Spotify, and calendar tools with household role permissions.",
        instructions=(
            "Use household capability tools whenever the user asks about weather, music, "
            "or calendar/schedule. After a tool returns, answer from the tool result; "
            "do not invent calendar events that are not in the returned result."
        ),
        tools=[get_weather, play_spotify, read_schedule, write_schedule],
    )


def get_weather(ctx: RunContext[Any], location: str = "home") -> dict:
    """Get weather for a location. Everyone can use this."""
    person = _require_person(ctx)
    return execute_capability(person, "weather", {"location": location}).model_dump()


def play_spotify(ctx: RunContext[Any], track: str) -> dict:
    """Play a Spotify track. Everyone can use this."""
    person = _require_person(ctx)
    return execute_capability(person, "spotify_play", {"track": track}).model_dump()


def read_schedule(ctx: RunContext[Any]) -> dict:
    """Read calendar/schedule events. Parents and children can use this."""
    person = _require_person(ctx)
    return execute_capability(person, "read_schedule", {}).model_dump()


def write_schedule(
    ctx: RunContext[Any],
    title: str,
    day: str | None = None,
    time: str | None = None,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> dict:
    """Create a calendar event. Only parents can use this."""
    person = _require_person(ctx)
    return execute_capability(
        person,
        "write_schedule",
        {
            "title": title,
            "day": day,
            "time": time,
            "start_time": start_time,
            "end_time": end_time,
        },
    ).model_dump()


def execute_capability(person: Person, action_type: str, params: dict) -> CapabilityResult:
    """Validate, permission-check, execute, audit, and format one capability call."""
    normalized_params = _normalize_params(person, action_type, params)
    permission_scope = _permission_scope_for_role(person.role)

    with Session(engine) as session:
        decision = check_permission(permission_scope, action_type, session)
        result = run_action(action_type, normalized_params) if decision == "allow" else None
        log_action(session, person.id, action_type, normalized_params, decision)

    return CapabilityResult(
        action_type=action_type,
        decision=decision,
        result=result,
        message=_message_for_result(action_type, decision, result),
    )


def _message_for_result(action_type: str, decision: str, result: dict | None) -> str:
    if decision != "allow":
        return "I can't do that for your role."

    if action_type == "read_schedule":
        events = result.get("events", []) if isinstance(result, dict) else []
        if not events:
            return "You don't have anything scheduled."
        event_titles = ", ".join(str(event.get("title", "Untitled")) for event in events)
        return f"Your scheduled events are: {event_titles}."

    if action_type == "write_schedule" and isinstance(result, dict):
        if result.get("status") == "created":
            return "Added that to the schedule."
        if result.get("status") == "error":
            return f"I couldn't add that to the schedule: {result.get('message')}."

    if action_type == "weather" and isinstance(result, dict):
        return (
            f"It's {result.get('condition')} and {result.get('temp_f')}°F in "
            f"{result.get('location')}. {result.get('advice')}."
        )

    if action_type == "spotify_play" and isinstance(result, dict):
        if result.get("status") == "queued":
            track = result.get("track", {})
            return f"Queued {track.get('name')} by {track.get('artist')}."
        if result.get("status") == "needs_spotify_auth":
            return result.get("message", "Connect Spotify first.")
        if result.get("status") == "queue_failed":
            return result.get("message", "No active Spotify device found.")
        if result.get("status") == "no_match":
            return "I couldn't find that track on Spotify."

    return "Done."


def _normalize_params(person: Person, action_type: str, params: dict) -> dict:
    if action_type == "weather":
        return WeatherParams.model_validate(params).model_dump()
    if action_type == "spotify_play":
        spotify = SpotifyParams.model_validate(params).model_dump()
        spotify["person_id"] = person.id
        return spotify
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


def _require_person(ctx: RunContext[Any]) -> Person:
    person = getattr(ctx.deps, "person", None)
    if person is None:
        raise RuntimeError("A person identity is required to use household capabilities.")
    return person


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
