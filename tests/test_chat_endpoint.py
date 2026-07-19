"""Chat endpoint tests using a fake model (no Ollama).

Covers:
* #3 — the reply is the model's actual output, never an echo of the user's msg.
* #6 — message_count is maintained on write and returned without re-parsing.
"""

from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.function import FunctionModel

from app.llm import agent


def _fixed_reply(text: str) -> FunctionModel:
    def fn(messages, info) -> ModelResponse:
        return ModelResponse(parts=[TextPart(text)])
    return FunctionModel(fn)


def _new_conversation(client, headers) -> int:
    return client.post("/conversations", headers=headers, json={}).json()["id"]


def test_reply_is_model_output(client, make_user):
    _, headers, _ = make_user("Alex")
    conv_id = _new_conversation(client, headers)

    with agent.override(model=_fixed_reply("HELLO")):
        r = client.post(f"/conversations/{conv_id}/messages", headers=headers,
                        json={"message": "hi there"}).json()

    assert r["reply"]["role"] == "assistant"
    assert r["reply"]["content"] == "HELLO"
    assert [m["role"] for m in r["messages"]] == ["user", "assistant"]


def test_reply_is_not_echo_of_user(client, make_user):
    """#3: the assistant reply must never be the user's own message."""
    _, headers, _ = make_user("Alex")
    conv_id = _new_conversation(client, headers)

    with agent.override(model=_fixed_reply("distinct answer")):
        r = client.post(f"/conversations/{conv_id}/messages", headers=headers,
                        json={"message": "my exact words"}).json()

    assert r["reply"]["content"] != "my exact words"
    assert r["reply"]["role"] == "assistant"


def test_message_count_tracks_turns(client, make_user):
    """#6: message_count is maintained and reflects user+assistant per turn."""
    _, headers, _ = make_user("Alex")
    conv_id = _new_conversation(client, headers)

    # Freshly created conversation has no messages.
    assert client.get("/conversations", headers=headers).json()[0]["message_count"] == 0

    with agent.override(model=_fixed_reply("ok")):
        client.post(f"/conversations/{conv_id}/messages", headers=headers,
                    json={"message": "turn one"})
        client.post(f"/conversations/{conv_id}/messages", headers=headers,
                    json={"message": "turn two"})

    convs = client.get("/conversations", headers=headers).json()
    assert convs[0]["message_count"] == 4  # 2 turns * (user + assistant)


def test_message_history_persists_across_requests(client, make_user):
    _, headers, _ = make_user("Alex")
    conv_id = _new_conversation(client, headers)

    with agent.override(model=_fixed_reply("first")):
        client.post(f"/conversations/{conv_id}/messages", headers=headers,
                    json={"message": "hello"})

    msgs = client.get(f"/conversations/{conv_id}/messages", headers=headers).json()
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[0]["content"] == "hello"
    assert msgs[1]["content"] == "first"
