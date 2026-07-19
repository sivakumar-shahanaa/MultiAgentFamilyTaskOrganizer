from sqlmodel import Session, select

from app.capabilities import execute_capability
from app.models import CalendarEvent
import app.integrations.spotify as spotify_integration
import app.main as main


def _admit(client, name: str, role: str, persona: str) -> str:
    login = client.post("/login", data={"name": name}, follow_redirects=False)
    request_id = login.headers["location"].split("=")[1]
    client.post("/admin/admit", data={"request_id": request_id, "role": role, "persona": persona})
    return client.get(f"/access-requests/{request_id}").json()["person_id"]


def _person(person_id: str):
    with Session(main.engine) as session:
        return session.get(main.Person, person_id)


def test_parent_write_schedule_capability_creates_calendar_event(client) -> None:
    person_id = _admit(client, "Parent One", "Parent", "julie")
    result = execute_capability(
        _person(person_id),
        "write_schedule",
        {"day": "Monday", "time": "6pm", "title": "Soccer Practice"},
    )

    assert result.decision == "allow"
    assert result.result["status"] == "created"
    assert result.message == "Added that to the schedule."
    with Session(main.engine) as session:
        events = session.exec(select(CalendarEvent)).all()
    assert len(events) == 1
    assert events[0].title == "Soccer Practice"
    assert events[0].owner_id == person_id


def test_child_cannot_write_schedule_capability(client) -> None:
    person_id = _admit(client, "Child One", "Child", "spencer")
    result = execute_capability(
        _person(person_id),
        "write_schedule",
        {"day": "Monday", "time": "6pm", "title": "Soccer Practice"},
    )

    assert result.decision == "deny"
    assert result.result is None
    assert result.message == "I can't do that for your role."
    with Session(main.engine) as session:
        events = session.exec(select(CalendarEvent)).all()
    assert events == []


def test_child_can_read_schedule_capability_without_hallucinated_events(client) -> None:
    person_id = _admit(client, "Child Two", "Child", "spencer")
    result = execute_capability(_person(person_id), "read_schedule", {})

    assert result.decision == "allow"
    assert result.result == {"status": "ok", "events": []}
    assert result.message == "You don't have anything scheduled."


def test_guest_can_use_weather_and_spotify_capabilities(client) -> None:
    person_id = _admit(client, "Guest One", "Guest", "guest")
    person = _person(person_id)

    weather = execute_capability(person, "weather", {"location": "home"})
    spotify = execute_capability(person, "spotify_play", {"track": "Espresso"})

    assert weather.decision == "allow"
    assert weather.result["location"] == "home"
    assert spotify.decision == "allow"
    assert spotify.result["status"] == "needs_spotify_auth"
    assert spotify.message.startswith("Connect Spotify first")


def test_spotify_capability_queues_track_with_connected_account(client, monkeypatch) -> None:
    person_id = _admit(client, "Spotify Parent", "Parent", "chris")
    person = _person(person_id)
    monkeypatch.setattr(spotify_integration, "get_valid_access_token", lambda session: "access-token")
    monkeypatch.setattr(
        spotify_integration,
        "search_track",
        lambda query, token: {"uri": "spotify:track:1", "name": "Espresso", "artist": "Sabrina Carpenter"},
    )
    monkeypatch.setattr(
        spotify_integration,
        "get_available_devices",
        lambda token: [{"id": "device-1", "name": "Kitchen Speaker", "is_active": False}],
    )
    monkeypatch.setattr(spotify_integration, "transfer_playback", lambda device_id, token: True)
    monkeypatch.setattr(spotify_integration, "add_to_queue", lambda uri, token, device_id=None: True)

    spotify = execute_capability(person, "spotify_play", {"track": "Espresso"})

    assert spotify.decision == "allow"
    assert spotify.result == {
        "status": "queued",
        "track": {"uri": "spotify:track:1", "name": "Espresso", "artist": "Sabrina Carpenter"},
        "device": "Kitchen Speaker",
        "activated_device": True,
    }
    assert spotify.message == "Queued Espresso by Sabrina Carpenter on Kitchen Speaker."


def test_chat_uses_plain_text_agent_reply(client, monkeypatch) -> None:
    person_id = _admit(client, "Chat User", "Guest", "guest")

    async def fake_run_turn(*args, **kwargs):
        return "Plain text reply from the Pydantic AI agent."

    monkeypatch.setattr(main, "run_turn", fake_run_turn)
    response = client.post("/chat/message", data={"person_id": person_id, "message": "hello"})

    assert "Plain text reply from the Pydantic AI agent." in response.text
