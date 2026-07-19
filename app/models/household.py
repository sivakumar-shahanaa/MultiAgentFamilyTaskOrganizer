from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field

class Profile(SQLModel, table=True):
    id: str = Field(primary_key=True)
    persona: str
    display_name: str
    avatar_url: Optional[str] = None

class Presence(SQLModel, table=True):
    profile_id: str = Field(primary_key=True, foreign_key="profile.id")
    location: str
    updated_at: datetime = Field(default_factory=datetime.utcnow)
