from datetime import datetime

from sqlmodel import Field, SQLModel


class SpotifyCredential(SQLModel, table=True):
    """Spotify OAuth tokens for the shared household Spotify account."""

    account_id: str = Field(default="household", primary_key=True)
    access_token: str
    refresh_token: str
    expires_at: datetime
