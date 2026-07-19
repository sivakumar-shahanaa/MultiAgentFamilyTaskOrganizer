from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field


class CalendarEvent(SQLModel, table=True):
    """A shared household calendar event."""

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    start_time: datetime
    end_time: datetime
    owner_id: str = Field(foreign_key="profile.id")
    visible_to: str = "household"    # "household" or comma-separated profile ids
