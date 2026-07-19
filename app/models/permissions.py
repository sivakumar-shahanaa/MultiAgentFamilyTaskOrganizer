from datetime import datetime
from typing import Optional

from sqlmodel import SQLModel, Field


class PermissionRule(SQLModel, table=True):
    """Deterministic lookup table: persona + action_type -> decision.

    This table is the whole permission engine. The model never decides
    this itself -- it only proposes an action_type + params.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    persona: str            # "kid" | "parent" | "guest"
    action_type: str        # "weather" | "spotify_play" | "read_schedule" | "write_schedule"
    decision: str            # "allow" | "deny" | "escalate"


class AuditLog(SQLModel, table=True):
    """Every proposed action and its outcome, regardless of branch taken."""

    id: Optional[int] = Field(default=None, primary_key=True)
    profile_id: str
    action_type: str
    params: str               # json.dumps(params)
    decision: str             # "allow" | "deny" | "escalate"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
