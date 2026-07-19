from sqlmodel import SQLModel, Session, create_engine

# SQLite for the hackathon MVP. Swap the URL for a Postgres/Supabase
# connection string later -- nothing else in the app needs to change.
DATABASE_URL = "sqlite:///household.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


def init_db() -> None:
    """Create tables if they don't exist. Call once at app startup."""
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
