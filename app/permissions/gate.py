import json
from datetime import datetime
from pathlib import Path
from sqlmodel import Session, select
from app.models import PermissionRule, AuditLog

DEFAULT_DECISION = "escalate"
JSONL_PATH = Path("household_audit.jsonl")

def check_permission(persona: str, action_type: str, session: Session) -> str:
    stmt = select(PermissionRule).where(PermissionRule.persona == persona, PermissionRule.action_type == action_type)
    rule = session.exec(stmt).first()
    return rule.decision if rule else DEFAULT_DECISION

def log_action(session: Session, profile_id: str, action_type: str, params: dict, decision: str) -> AuditLog:
    entry = AuditLog(profile_id=profile_id, action_type=action_type, params=json.dumps(params), decision=decision, timestamp=datetime.utcnow())
    session.add(entry); session.commit(); session.refresh(entry)
    try:
        with JSONL_PATH.open("a") as f:
            f.write(json.dumps({"profile_id":profile_id,"action_type":action_type,"params":params,"decision":decision,"timestamp":entry.timestamp.isoformat()})+"\n")
    except OSError:
        pass
    return entry
