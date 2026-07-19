from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from app.db.session import get_session
from app.permissions.gate import check_permission, log_action
from app.integrations.registry import run_action

router = APIRouter(prefix="/actions", tags=["actions"])


class ActionRequest(BaseModel):
    profile_id: str
    persona: str
    action_type: str
    params: dict = {}


@router.post("")
async def propose_action(req: ActionRequest, session: Session = Depends(get_session)):
    decision = check_permission(req.persona, req.action_type, session)

    result = None
    if decision == "allow":
        result = await run_action(req.action_type, req.params, session)

    log_action(session, req.profile_id, req.action_type, req.params, decision)

    return {"decision": decision, "result": result}
