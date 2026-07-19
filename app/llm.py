"""Agent layer over an OpenAI-compatible local LLM (Ollama, LM Studio, vLLM...).

Refactored from the per-message ``LocalChatAgent`` into the target pattern:

* ONE module-level ``Agent`` definition (stateless).
* Per-user state passed at run time via a typed ``AgentDeps`` object.
* Persona injected through dynamic ``@agent.instructions``, layered under a
  fixed base prompt the app controls. Instructions (unlike system prompts) are
  re-applied on every run and are NOT stored in the message history, so the
  current persona always takes effect and edits apply immediately.
* Conversation history handled with Pydantic AI's native ``message_history``
  (serialized to/from JSON) instead of a flattened text transcript — this
  round-trips tool calls once Phase 3 (RAG tools) lands.

``AgentDeps`` already carries ``user_id`` so Phase 3 can hang user-scoped
``recall``/``remember`` tools off it with the isolation boundary intact.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv
from pydantic_ai import Agent, RunContext

try:
    from pydantic_ai.models.openai import OpenAIModel
except ImportError:  # newer pydantic-ai renamed this class
    from pydantic_ai.models.openai import OpenAIChatModel as OpenAIModel
from pydantic_ai.messages import (
    ModelMessagesTypeAdapter,
    TextPart,
    UserPromptPart,
)
from pydantic_ai.providers.openai import OpenAIProvider

from app.schemas import ChatMessage
from app.utils import utcnow

load_dotenv()

DEFAULT_MODEL = os.getenv("LOCAL_LLM_MODEL", "llama3.2")
DEFAULT_BASE_URL = os.getenv("LOCAL_LLM_BASE_URL", "http://localhost:11434/v1")
DEFAULT_API_KEY = os.getenv("LOCAL_LLM_API_KEY", "ollama")

# Fixed instructions the app owns. The user's persona is appended UNDER this so
# it can shape voice/behavior but not override tool-use or safety guidance.
BASE_PROMPT = (
    "You are a personal assistant for one member of a household, helping them "
    "organize tasks and chores. Be concise and practical."
)


@dataclass
class AgentDeps:
    """Per-user state handed to the agent for a single run."""

    user_id: int
    user_name: str
    persona_prompt: str | None = None


_provider = OpenAIProvider(base_url=DEFAULT_BASE_URL, api_key=DEFAULT_API_KEY)
_model_cache: dict[str, OpenAIModel] = {}


def _get_model(name: str) -> OpenAIModel:
    if name not in _model_cache:
        _model_cache[name] = OpenAIModel(name, provider=_provider)
    return _model_cache[name]


# Single, module-level agent. Bound to the default model; per-user overrides are
# passed to ``run(model=...)`` below.
# Ollama's Qwen 3 models think by default. Disable that hidden reasoning trace
# so interactive replies return promptly; the app only needs the final answer.
agent = Agent(
    _get_model(DEFAULT_MODEL),
    deps_type=AgentDeps,
    model_settings={"extra_body": {"think": False}},
)


@agent.instructions
def _base_instructions(ctx: RunContext[AgentDeps]) -> str:
    return BASE_PROMPT


@agent.instructions
def _persona_instructions(ctx: RunContext[AgentDeps]) -> str:
    persona = (ctx.deps.persona_prompt or "").strip()
    if not persona:
        return ""
    # Clearly framed as user-provided so it reads as a request, not an override.
    return (
        f"You are speaking with {ctx.deps.user_name}. They have configured the "
        f"following persona for you:\n{persona}"
    )


async def run_chat(
    *,
    user_id: int,
    user_name: str,
    persona_prompt: str | None,
    model_name: str | None,
    message: str,
    history_json: str,
) -> tuple[str, str]:
    """Run one turn.

    Returns ``(reply_text, updated_history_json)``. The caller persists the
    updated history back onto the Conversation.
    """
    history = ModelMessagesTypeAdapter.validate_json(history_json or "[]")
    deps = AgentDeps(user_id=user_id, user_name=user_name, persona_prompt=persona_prompt)

    result = await agent.run(
        message,
        message_history=history,
        deps=deps,
        model=_get_model(model_name or DEFAULT_MODEL),
    )

    reply_text = str(getattr(result, "output", None) or getattr(result, "data", ""))
    # Instructions aren't stored in message history, so persisting all_messages()
    # keeps only the user/assistant exchange — the current persona is re-applied
    # fresh on every run (and edits take effect immediately).
    updated_json = ModelMessagesTypeAdapter.dump_json(result.all_messages()).decode()
    return reply_text, updated_json


def history_to_display(history_json: str) -> list[ChatMessage]:
    """Derive simple role/content messages from stored Pydantic AI history."""
    if not history_json:
        return []
    messages = ModelMessagesTypeAdapter.validate_json(history_json)
    out: list[ChatMessage] = []
    for m in messages:
        for part in m.parts:
            if isinstance(part, UserPromptPart):
                content = part.content if isinstance(part.content, str) else str(part.content)
                out.append(
                    ChatMessage(
                        role="user",
                        content=content,
                        created_at=getattr(part, "timestamp", None) or utcnow(),
                    )
                )
            elif isinstance(part, TextPart):
                out.append(
                    ChatMessage(
                        role="assistant",
                        content=part.content,
                        created_at=getattr(part, "timestamp", None) or utcnow(),
                    )
                )
    return out
