from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field

class PermissionRule(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    persona: str
    action_type: str
    decision: str

class AuditLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    profile_id: str
    action_type: str
    params: str
    decision: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
