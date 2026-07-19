"""Shared test fixtures.

Points the app at a throwaway SQLite file BEFORE importing any app module (the
engine binds to DATABASE_URL at import time), and gives each test a fresh schema
so tests are isolated from each other.
"""

import os
import pathlib
import tempfile

# Must run before importing app.db / app.main.
_TMP_DIR = tempfile.mkdtemp(prefix="mafto_tests_")
_DB_PATH = pathlib.Path(_TMP_DIR, "test.db").as_posix()
os.environ["DATABASE_URL"] = f"sqlite:///{_DB_PATH}"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import SQLModel  # noqa: E402

from app.db import engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def client():
    # Fresh schema per test.
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def make_user(client):
    """Factory: create a user and return (token, auth_headers, body)."""
    def _make(name="Alex", **kwargs):
        body = client.post("/users", json={"name": name, **kwargs}).json()
        return body["token"], {"X-API-Token": body["token"]}, body
    return _make
