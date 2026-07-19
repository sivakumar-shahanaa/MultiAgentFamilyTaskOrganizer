from app.db import engine as app_engine
from app.db.session import engine as capability_engine


def test_capabilities_use_unified_app_database_engine() -> None:
    assert capability_engine is app_engine
