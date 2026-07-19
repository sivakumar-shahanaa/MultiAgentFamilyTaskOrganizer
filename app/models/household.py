from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field


class Profile(SQLModel, table=True):
    """A household member or guest. Identity -> persona -> permission scope."""

    id: str = Field(primary_key=True)            # e.g. "parent_1", "kid_1", "guest_1"
    persona: str                                    # "parent" | "kid" | "guest"
    display_name: str
    avatar_url: Optional[str] = None


class Presence(SQLModel, table=True):
    """Where each profile currently is. Used for proactive briefings / traffic planning."""

    profile_id: str = Field(primary_key=True, foreign_key="profile.id")
    location: str                                   # "home" | "school" | "work" | "unknown"
    updated_at: datetime = Field(default_factory=datetime.utcnow)
