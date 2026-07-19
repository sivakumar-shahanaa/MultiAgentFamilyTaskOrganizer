from sqlmodel import Session, select

from app.db.session import engine, init_db
from app.models import Profile, PermissionRule


DEFAULT_PROFILES = [
    Profile(id="parent_1", persona="parent", display_name="Parent"),
    Profile(id="kid_1", persona="kid", display_name="Kid"),
    Profile(id="guest_1", persona="guest", display_name="Guest"),
]

DEFAULT_RULES = [
    # persona, action_type, decision
    ("parent", "send_email", "allow"),
    ("parent", "reschedule_calendar", "allow"),
    ("parent", "spotify_play", "allow"),
    ("parent", "weather", "allow"),

    ("kid", "send_email", "escalate"),
    ("kid", "reschedule_calendar", "escalate"),
    ("kid", "spotify_play", "allow"),
    ("kid", "weather", "allow"),

    ("guest", "send_email", "deny"),
    ("guest", "reschedule_calendar", "deny"),
    ("guest", "spotify_play", "allow"),
    ("guest", "weather", "allow"),
]


def seed() -> None:
    init_db()
    with Session(engine) as session:
        for profile in DEFAULT_PROFILES:
            existing = session.get(Profile, profile.id)
            if not existing:
                session.add(profile)

        for persona, action_type, decision in DEFAULT_RULES:
            stmt = select(PermissionRule).where(
                PermissionRule.persona == persona,
                PermissionRule.action_type == action_type,
            )
            existing = session.exec(stmt).first()
            if not existing:
                session.add(
                    PermissionRule(
                        persona=persona,
                        action_type=action_type,
                        decision=decision,
                    )
                )

        session.commit()
    print("Seed complete.")


if __name__ == "__main__":
    seed()
