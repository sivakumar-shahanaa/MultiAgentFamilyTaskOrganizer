"""Agent factory — one Pydantic AI agent per persona, all against one ollama.

make_agent(persona_key) returns a cached Agent whose system prompt is the
persona voice and whose output is schema-validated ProposedAction.

Structured-output mode chosen empirically (2026-07-19, gemma3:4b):
- NativeOutput: ollama's grammar-constrained decoding forces the free-form
  `params` dict to `{}` every time -> unusable.
- PromptedOutput: fills params, but the 4B sometimes echoes the schema
  envelope ({"properties": {...}}) and then retry-spirals -> flaky.
- So: TextOutput + a lenient shim that unwraps that one known envelope and
  strips code fences, with Pydantic doing ALL real validation and ModelRetry
  driving the auto-retry (retries=2). The shim is not a parser — json.loads
  + model_validate remain the only parsing.
"""
import json
import os
from dataclasses import dataclass
from datetime import datetime

from dotenv import load_dotenv
from pydantic import ValidationError
from pydantic_ai import Agent, ModelRetry, RunContext, TextOutput
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from app.capabilities import execute_capability
from app.contracts import ProposedAction
from app.db import Person
from app.personas import PERSONAS


def parse_proposed_action(text: str) -> ProposedAction:
    """Lenient decode of the model's reply into a validated ProposedAction."""
    raw = text.strip()
    if raw.startswith("```"):  # ```json ... ``` fences
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        raw = raw.rsplit("```", 1)[0].strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ModelRetry(
            "Reply must be ONLY a JSON object with keys action, params, reply."
        ) from e
    if isinstance(data, dict) and "action" not in data:
        for key in ("properties", "output", "response"):  # observed envelopes
            if isinstance(data.get(key), dict) and "action" in data[key]:
                data = data[key]
                break
    try:
        return ProposedAction.model_validate(data)
    except ValidationError as e:
        raise ModelRetry(f"JSON did not match the required shape: {e}") from e

load_dotenv()

MODEL_NAME = os.getenv("LOCAL_LLM_MODEL", "gemma3:4b")
BASE_URL = os.getenv("LOCAL_LLM_BASE_URL", "http://localhost:11434/v1")
API_KEY = os.getenv("LOCAL_LLM_API_KEY", "ollama")

@dataclass
class AgentDeps:
    person: Person | None = None


_agents: dict[str, Agent] = {}


def make_agent(persona_key: str) -> Agent:
    """Agent for a persona. Cached — agents are stateless and reusable;
    per-conversation state lives in Session.history, not here."""
    if persona_key not in PERSONAS:
        raise KeyError(f"unknown persona {persona_key!r}; expected one of {list(PERSONAS)}")
    if persona_key not in _agents:
        provider = OpenAIProvider(base_url=BASE_URL, api_key=API_KEY)
        model = OpenAIChatModel(MODEL_NAME, provider=provider)
        agent = Agent(
            model,
            instructions=PERSONAS[persona_key].system_prompt,
            deps_type=AgentDeps,
            output_type=TextOutput(parse_proposed_action),
            retries=2,
            model_settings={"temperature": 0.3},
        )
        _register_capability_tools(agent)
        _agents[persona_key] = agent
    return _agents[persona_key]


def _register_capability_tools(agent: Agent) -> None:
    @agent.tool
    def get_weather(ctx: RunContext[AgentDeps], location: str = "home") -> dict:
        """Get weather for a location. Everyone can use this."""
        person = _require_person(ctx)
        return execute_capability(person, "weather", {"location": location}).model_dump()

    @agent.tool
    def play_spotify(ctx: RunContext[AgentDeps], track: str) -> dict:
        """Play a Spotify track. Everyone can use this."""
        person = _require_person(ctx)
        return execute_capability(person, "spotify_play", {"track": track}).model_dump()

    @agent.tool
    def read_schedule(ctx: RunContext[AgentDeps]) -> dict:
        """Read calendar/schedule events. Parents and children can use this."""
        person = _require_person(ctx)
        return execute_capability(person, "read_schedule", {}).model_dump()

    @agent.tool
    def write_schedule(
        ctx: RunContext[AgentDeps],
        title: str,
        day: str | None = None,
        time: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> dict:
        """Create a calendar event. Only parents can use this."""
        person = _require_person(ctx)
        return execute_capability(
            person,
            "write_schedule",
            {
                "title": title,
                "day": day,
                "time": time,
                "start_time": start_time,
                "end_time": end_time,
            },
        ).model_dump()


def _require_person(ctx: RunContext[AgentDeps]) -> Person:
    if ctx.deps.person is None:
        raise ModelRetry("A person identity is required to use capabilities.")
    return ctx.deps.person


async def run_turn(
    persona_key: str,
    user_text: str,
    history: list[dict] | None = None,
    person: Person | None = None,
) -> ProposedAction:
    """One conversation turn -> validated ProposedAction.

    History is passed as plain [{role, content}] dicts (the Session.history
    shape) and folded into the prompt, keeping the wire format teammate-simple.
    """
    agent = make_agent(persona_key)
    prompt = user_text
    if history:
        transcript = "\n".join(f"{m['role']}: {m['content']}" for m in history)
        prompt = f"Conversation so far:\n{transcript}\n\nuser: {user_text}"
    result = await agent.run(prompt, deps=AgentDeps(person=person))
    return result.output
