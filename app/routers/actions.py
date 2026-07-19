from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from app.db.session import get_session
from app.permissions.gate import check_permission, log_action
from app.integrations.registry import run_action

router = APIRouter(prefix="/actions", tags=["actions"])


class ActionRequest(BaseModel):
    profile_id: str
    persona: str          # "parent" | "kid" | "guest"
    action_type: str      # "weather" | "spotify_play" | "read_schedule" | "write_schedule"
    params: dict = {}


@router.post("")
def propose_action(req: ActionRequest, session: Session = Depends(get_session)):
    """The whole pipeline in one endpoint: model proposes, gate disposes,
    integration executes (if allowed), every outcome is logged.
    """
    decision = check_permission(req.persona, req.action_type, session)

    result = None
    if decision == "allow":
        result = run_action(req.action_type, req.params)

    log_action(session, req.profile_id, req.action_type, req.params, decision)

    return {"decision": decision, "result": result}
