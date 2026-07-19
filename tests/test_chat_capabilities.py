from sqlmodel import Session, select

from app.contracts import ProposedAction
from app.models import CalendarEvent
import app.main as main


async def _propose(action: str, params: dict | None = None) -> ProposedAction:
    return ProposedAction(action=action, params=params or {}, reply="Proposed.")


def _admit(client, name: str, role: str, persona: str) -> str:
    login = client.post("/login", data={"name": name}, follow_redirects=False)
    request_id = login.headers["location"].split("=")[1]
    client.post("/admin/admit", data={"request_id": request_id, "role": role, "persona": persona})
    return client.get(f"/access-requests/{request_id}").json()["person_id"]


def test_parent_can_write_schedule_from_chat(client, monkeypatch) -> None:
    person_id = _admit(client, "Parent One", "Parent", "julie")

    async def fake_run_turn(*args, **kwargs):
        return await _propose(
            "write_schedule",
            {"day": "Monday", "time": "6pm", "title": "Soccer Practice"},
        )

    monkeypatch.setattr(main, "run_turn", fake_run_turn)
    response = client.post("/chat/message", data={"person_id": person_id, "message": "Add soccer Monday at 6"})

    assert "Added that to the schedule." in response.text
    assert "Action executed: write_schedule" in response.text
    with Session(main.engine) as session:
        events = session.exec(select(CalendarEvent)).all()
    assert len(events) == 1
    assert events[0].title == "Soccer Practice"
    assert events[0].owner_id == person_id


def test_child_cannot_write_schedule_from_chat(client, monkeypatch) -> None:
    person_id = _admit(client, "Child One", "Child", "spencer")

    async def fake_run_turn(*args, **kwargs):
        return await _propose("write_schedule", {"action": "list"})

    monkeypatch.setattr(main, "run_turn", fake_run_turn)
    response = client.post("/chat/message", data={"person_id": person_id, "message": "Update the schedule"})

    assert "Action deny: write_schedule" in response.text


def test_child_can_read_schedule_from_chat(client, monkeypatch) -> None:
    person_id = _admit(client, "Child Two", "Child", "spencer")

    async def fake_run_turn(*args, **kwargs):
        return ProposedAction(action="read_schedule", params={}, reply="You have meetings all day today.")

    monkeypatch.setattr(main, "run_turn", fake_run_turn)
    response = client.post("/chat/message", data={"person_id": person_id, "message": "What's on the schedule?"})

    assert "You don&#x27;t have anything scheduled." in response.text
    assert "meetings all day" not in response.text
    assert "Action executed: read_schedule" in response.text


def test_guest_can_use_weather_and_spotify_from_chat(client, monkeypatch) -> None:
    person_id = _admit(client, "Guest One", "Guest", "guest")
    proposed_actions = iter([
        ProposedAction(action="weather", params={"location": "home"}, reply="Weather."),
        ProposedAction(action="spotify_play", params={"track": "Espresso"}, reply="Music."),
    ])

    async def fake_run_turn(*args, **kwargs):
        return next(proposed_actions)

    monkeypatch.setattr(main, "run_turn", fake_run_turn)

    weather = client.post("/chat/message", data={"person_id": person_id, "message": "weather"})
    spotify = client.post("/chat/message", data={"person_id": person_id, "message": "music"})

    assert "Action executed: weather" in weather.text
    assert "Action executed: spotify_play" in spotify.text
