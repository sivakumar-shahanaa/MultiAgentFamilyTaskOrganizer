"""Shared database session for household capability routes.

This module intentionally re-exports the unified app database engine/session so
Sahana's capability models live in the same SQLite DB as identity and chat.
"""

from app.db import engine, get_session, init_db

__all__ = ["engine", "get_session", "init_db"]
