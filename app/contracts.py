"""Shared team contracts — the API between workstreams.

Everyone imports from here; nobody redefines these shapes.
- Robyn: agents produce ProposedAction, sessions carry persona+role
- Patrick & Binam: check_permission(role, action) -> Decision (see permissions_stub)
- Sahanaa: executor + shared state consume allowed ProposedActions
- Peter: WS payloads serialize these models

Persona = VOICE (how the assistant talks to this person).
Role    = PERMISSION SCOPE (what this person may do).
Two parents and two kids share roles; the permission table stays 3 rows.
"""
from typing import Literal

from pydantic import BaseModel, Field, computed_field

# --- identity ---------------------------------------------------------------

PersonaKey = Literal["chris", "julie", "spencer", "marta", "guest"]
Role = Literal["parent", "kid", "guest"]

PERSONA_ROLE: dict[str, Role] = {
    "chris": "parent",   # dad, works from home
    "julie": "parent",   # mom
    "spencer": "kid",    # high schooler
    "marta": "kid",      # youngest
    "guest": "guest",    # occasional visitor
}

# --- model output -----------------------------------------------------------


class ProposedAction(BaseModel):
    """What the LLM returns. It never acts — it proposes."""

    action: Literal[
        "play_music", "add_event", "get_weather",
        "send_message", "save_note", "none",
    ]
    params: dict = Field(default_factory=dict)
    reply: str = Field(description="What to say to the user, in persona voice")
    # 'none' = pure conversation, no action needed


# --- permission engine (Patrick & Binam implement) --------------------------


class Decision(BaseModel):
    verdict: Literal["allow", "deny", "escalate"]
    reason: str


# --- session ----------------------------------------------------------------


class Session(BaseModel):
    id: str
    persona: PersonaKey
    history: list[dict] = Field(default_factory=list)  # [{role, content}]

    @computed_field  # serialized alongside persona so consumers never re-derive
    @property
    def role(self) -> Role:
        return PERSONA_ROLE[self.persona]
