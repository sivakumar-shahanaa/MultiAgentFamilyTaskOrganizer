"""Persona agent factory using Pydantic AI capabilities."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from app.capabilities import household_capability
from app.db import Person
from app.personas import PERSONAS

load_dotenv()

MODEL_NAME = os.getenv("LOCAL_LLM_MODEL", "gemma3:4b")
BASE_URL = os.getenv("LOCAL_LLM_BASE_URL", "http://localhost:11434/v1")
API_KEY = os.getenv("LOCAL_LLM_API_KEY", "ollama")


@dataclass
class AgentDeps:
    person: Person


_agents: dict[str, Agent[AgentDeps, str]] = {}


def make_agent(persona_key: str) -> Agent[AgentDeps, str]:
    """Return a cached persona agent with household capabilities attached."""
    if persona_key not in PERSONAS:
        raise KeyError(f"unknown persona {persona_key!r}; expected one of {list(PERSONAS)}")
    if persona_key not in _agents:
        provider = OpenAIProvider(base_url=BASE_URL, api_key=API_KEY)
        model = OpenAIChatModel(MODEL_NAME, provider=provider)
        _agents[persona_key] = Agent(
            model,
            instructions=PERSONAS[persona_key].system_prompt,
            deps_type=AgentDeps,
            capabilities=[household_capability()],
            retries=2,
            model_settings={"temperature": 0.3},
        )
    return _agents[persona_key]


async def run_turn(
    persona_key: str,
    user_text: str,
    history: list[dict] | None,
    person: Person,
) -> str:
    """Run one chat turn. Capability/tool calls happen inside Pydantic AI."""
    agent = make_agent(persona_key)
    prompt = user_text
    if history:
        transcript = "\n".join(f"{m['role']}: {m['content']}" for m in history)
        prompt = f"Conversation so far:\n{transcript}\n\nuser: {user_text}"
    result = await agent.run(prompt, deps=AgentDeps(person=person))
    return str(result.output if hasattr(result, "output") else result.data)
