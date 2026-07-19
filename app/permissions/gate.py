import json
from datetime import datetime
from pathlib import Path

from sqlmodel import Session, select

from app.models import PermissionRule, AuditLog

# Fail-safe default: if no rule matches, never silently allow.
DEFAULT_DECISION = "escalate"

# Append-only JSONL trail -- separate from the queryable AuditLog table.
# Good for `tail -f` during a demo; the SQL table is good for querying later.
JSONL_PATH = Path("household_audit.jsonl")


def check_permission(persona: str, action_type: str, session: Session) -> str:
    """Deterministic lookup: persona + action_type -> allow / deny / escalate.

    This is intentionally dumb -- a table lookup, not a model call.
    The LLM proposes; this function disposes.
    """
    stmt = select(PermissionRule).where(
        PermissionRule.persona == persona,
        PermissionRule.action_type == action_type,
    )
    rule = session.exec(stmt).first()
    return rule.decision if rule else DEFAULT_DECISION


def log_action(
    session: Session,
    profile_id: str,
    action_type: str,
    params: dict,
    decision: str,
) -> AuditLog:
    entry = AuditLog(
        profile_id=profile_id,
        action_type=action_type,
        params=json.dumps(params),
        decision=decision,
        timestamp=datetime.utcnow(),
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)

    # Mirror to append-only JSONL. Best-effort: a write failure here should
    # never break the request, since the SQL row is already the source of truth.
    try:
        with JSONL_PATH.open("a") as f:
            f.write(
                json.dumps(
                    {
                        "profile_id": profile_id,
                        "action_type": action_type,
                        "params": params,
                        "decision": decision,
                        "timestamp": entry.timestamp.isoformat(),
                    }
                )
                + "\n"
            )
    except OSError:
        pass

    return entry
