"""Shared team contracts.

Persona = VOICE (how the assistant talks to this person).
Role    = PERMISSION SCOPE (what this person may do).

Capabilities are now exposed to agents as Pydantic AI tools in
``app.capabilities`` instead of as model-produced ProposedAction JSON.
"""
from typing import Literal

from pydantic import BaseModel, Field, computed_field

# --- identity ---------------------------------------------------------------

PersonaKey = Literal["chris", "julie", "spencer", "marta", "guest"]
Role = Literal["parent", "kid", "guest"]

PERSONA_ROLE: dict[str, Role] = {
    "chris": "parent",
    "julie": "parent",
    "spencer": "kid",
    "marta": "kid",
    "guest": "guest",
}


class Decision(BaseModel):
    verdict: Literal["allow", "deny", "escalate"]
    reason: str


class Session(BaseModel):
    id: str
    persona: PersonaKey
    history: list[dict] = Field(default_factory=list)

    @computed_field
    @property
    def role(self) -> Role:
        return PERSONA_ROLE[self.persona]
