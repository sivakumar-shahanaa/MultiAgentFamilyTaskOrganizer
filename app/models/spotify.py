from datetime import datetime

from sqlmodel import Field, SQLModel


class SpotifyCredential(SQLModel, table=True):
    """Spotify OAuth tokens for an admitted Person."""

    person_id: str = Field(primary_key=True, foreign_key="person.id")
    access_token: str
    refresh_token: str
    expires_at: datetime
