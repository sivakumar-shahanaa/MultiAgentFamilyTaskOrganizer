"""API tests: users, tokens, auth, and cross-user isolation.

The isolation tests guard the security boundary — one household member must
never be able to read or address another member's conversations.
"""


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


# --- Users / personas ---------------------------------------------------------

def test_create_user_returns_token(make_user):
    _, _, body = make_user("Alex", persona_prompt="Be terse.")
    assert body["token"]
    assert body["name"] == "Alex"
    assert body["persona_prompt"] == "Be terse."


def test_tokens_are_distinct(make_user):
    _, _, a = make_user("Alex")
    _, _, b = make_user("Bailey")
    assert a["token"] != b["token"]


def test_duplicate_name_conflicts(client, make_user):
    make_user("Alex")
    assert client.post("/users", json={"name": "Alex"}).status_code == 409


def test_me_requires_valid_token(client, make_user):
    assert client.get("/users/me").status_code == 401
    assert client.get("/users/me", headers={"X-API-Token": "nope"}).status_code == 401
    _, headers, _ = make_user("Alex")
    assert client.get("/users/me", headers=headers).json()["name"] == "Alex"


def test_me_hides_token(client, make_user):
    _, headers, _ = make_user("Alex")
    me = client.get("/users/me", headers=headers).json()
    assert me["name"] == "Alex"
    assert "token" not in me


def test_update_persona(client, make_user):
    _, headers, _ = make_user("Alex", persona_prompt="Be terse.")
    updated = client.patch("/users/me", headers=headers,
                           json={"persona_prompt": "Be a coach."}).json()
    assert updated["persona_prompt"] == "Be a coach."


def test_roster_lists_users_without_tokens(client, make_user):
    make_user("Alex")
    make_user("Bailey")
    roster = client.get("/users").json()
    assert len(roster) == 2
    assert all("token" not in u for u in roster)


# --- Conversations / isolation ------------------------------------------------

def test_conversation_is_scoped_to_owner(client, make_user):
    _, alex, _ = make_user("Alex")
    _, bailey, _ = make_user("Bailey")

    client.post("/conversations", headers=alex, json={"title": "Today"})

    assert len(client.get("/conversations", headers=alex).json()) == 1
    assert len(client.get("/conversations", headers=bailey).json()) == 0


def test_cross_user_conversation_access_is_blocked(client, make_user):
    """Security: Bailey must not read Alex's conversation (404, not 403, so
    existence isn't leaked)."""
    _, alex, _ = make_user("Alex")
    _, bailey, _ = make_user("Bailey")

    conv_id = client.post("/conversations", headers=alex, json={}).json()["id"]

    assert client.get(f"/conversations/{conv_id}/messages", headers=bailey).status_code == 404
    # Owner can read their own (empty) thread.
    r = client.get(f"/conversations/{conv_id}/messages", headers=alex)
    assert r.status_code == 200 and r.json() == []


def test_conversation_requires_auth(client):
    assert client.get("/conversations").status_code == 401
    assert client.post("/conversations", json={}).status_code == 401
