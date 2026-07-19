from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field


class SpotifyCredential(SQLModel, table=True):
    """Spotify OAuth tokens for a profile. In practice only the parent
    profile will have one of these -- kids/guests never authenticate with
    Spotify directly, they just submit requests that ride on the host's
    authenticated session.
    """

    profile_id: str = Field(primary_key=True, foreign_key="profile.id")
    access_token: str
    refresh_token: str
    expires_at: datetime
