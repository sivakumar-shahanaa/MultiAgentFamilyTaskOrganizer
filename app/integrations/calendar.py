from datetime import datetime

from sqlmodel import Session, select

from app.db.session import engine
from app.integrations.base import Integration
from app.models import CalendarEvent


class CalendarIntegration(Integration):
    """Reads/writes CalendarEvent directly for the MVP. Replace with a real
    Google Calendar OAuth call later -- keep the same params/return shape.
    """

    def execute(self, params: dict) -> dict:
        action = params.get("action", "list")

        with Session(engine) as session:
            if action == "create":
                event = CalendarEvent(
                    title=params["title"],
                    start_time=datetime.fromisoformat(params["start_time"]),
                    end_time=datetime.fromisoformat(params["end_time"]),
                    owner_id=params["owner_id"],
                    visible_to=params.get("visible_to", "household"),
                )
                session.add(event)
                session.commit()
                session.refresh(event)
                return {"status": "created", "event_id": event.id}

            if action == "reschedule":
                event = session.get(CalendarEvent, params["event_id"])
                if not event:
                    return {"status": "not_found"}
                event.start_time = datetime.fromisoformat(params["start_time"])
                event.end_time = datetime.fromisoformat(params["end_time"])
                session.add(event)
                session.commit()
                return {"status": "rescheduled", "event_id": event.id}

            # default: list
            events = session.exec(select(CalendarEvent)).all()
            return {"status": "ok", "events": [e.model_dump() for e in events]}
