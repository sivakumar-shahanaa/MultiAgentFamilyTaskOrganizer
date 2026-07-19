"""Regression tests for the persona/instructions wiring.

These lock down a bug where base prompt + persona were implemented with
``@agent.system_prompt``. Because system prompts are only generated for an
empty history (and were stripped before persisting), the model received NO
system prompt from the second turn onward, and persona edits never applied —
silently defeating the whole persona feature.

The fix uses ``@agent.instructions`` (re-applied every run, not stored in
history). If someone reverts to system prompts, TURN 2 assertions here fail.

A fake ``FunctionModel`` captures exactly what the model receives, so these
run without Ollama.
"""

import asyncio

from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from app.llm import BASE_PROMPT, agent, run_chat


def _capture():
    """Returns (model, seen) where seen[i] is the instructions text the model
    received on the i-th run."""
    seen: list[str] = []

    def fn(messages, info: AgentInfo) -> ModelResponse:
        seen.append(info.instructions or "")
        return ModelResponse(parts=[TextPart("ok")])

    return FunctionModel(fn), seen


def _run(**kwargs) -> tuple[str, str]:
    return asyncio.run(run_chat(**kwargs))


def test_base_and_persona_present_on_first_turn():
    model, seen = _capture()
    with agent.override(model=model):
        _run(user_id=1, user_name="Alex", persona_prompt="Be terse.",
             model_name=None, message="hi", history_json="[]")
    assert BASE_PROMPT in seen[0]
    assert "Be terse." in seen[0]


def test_base_and_persona_survive_to_second_turn():
    """The core regression: turn 2 previously got an EMPTY system prompt."""
    model, seen = _capture()
    with agent.override(model=model):
        _, history = _run(user_id=1, user_name="Alex", persona_prompt="Be terse.",
                          model_name=None, message="hi", history_json="[]")
        # Second turn reuses the persisted history from the first.
        _run(user_id=1, user_name="Alex", persona_prompt="Be terse.",
             model_name=None, message="again", history_json=history)

    assert len(seen) == 2
    assert BASE_PROMPT in seen[1], "base prompt missing on turn 2"
    assert "Be terse." in seen[1], "persona missing on turn 2"


def test_persona_edit_takes_effect_immediately():
    """Editing the persona must change what the model sees on the next turn,
    even when replaying prior history that embedded the old persona."""
    model, seen = _capture()
    with agent.override(model=model):
        _, history = _run(user_id=1, user_name="Alex", persona_prompt="Be terse.",
                          model_name=None, message="hi", history_json="[]")
        _run(user_id=1, user_name="Alex", persona_prompt="Be VERBOSE now.",
             model_name=None, message="again", history_json=history)

    assert "Be VERBOSE now." in seen[1]
    assert "Be terse." not in seen[1], "stale persona leaked from history"


def test_no_persona_is_tolerated():
    model, seen = _capture()
    with agent.override(model=model):
        _run(user_id=1, user_name="Alex", persona_prompt=None,
             model_name=None, message="hi", history_json="[]")
    # Base prompt still applies; no persona clause.
    assert BASE_PROMPT in seen[0]
    assert "configured the following persona" not in seen[0]


def test_persona_not_leaked_into_display_history():
    """Instructions must not surface as chat messages in the stored transcript."""
    from app.llm import history_to_display

    model, _ = _capture()
    with agent.override(model=model):
        _, history = _run(user_id=1, user_name="Alex", persona_prompt="Be terse.",
                          model_name=None, message="hi", history_json="[]")

    display = history_to_display(history)
    assert [m.role for m in display] == ["user", "assistant"]
    assert all("Be terse." not in m.content for m in display)
