"""
Shared pytest fixtures for the StackTrace.run backend.

Each test gets an isolated temporary SQLite database (via monkeypatching
settings.LOCAL_SQLITE_PATH), so the real local_dev.db is never touched and tests
never bleed state into each other.
"""

import sys
from pathlib import Path

import pytest

# Make the backend package importable (config, db, app, ...).
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import config  # noqa: E402


@pytest.fixture
def db_ready(tmp_path, monkeypatch):
    """Point the DB layer at a throwaway SQLite file and create the schema.

    Force local SQLite even if a Turso DATABASE_URL is present in the env, so the
    suite never touches a real Turso database.
    """
    db_file = tmp_path / "test.db"
    monkeypatch.setattr(config.settings, "DATABASE_URL", None)
    monkeypatch.setattr(config.settings, "TURSO_AUTH_TOKEN", None)
    monkeypatch.setattr(config.settings, "LOCAL_SQLITE_PATH", str(db_file))
    import db  # imported lazily so the patched path is in effect
    db.init_db()
    return db_file


@pytest.fixture
def client(db_ready):
    """Flask test client wired to the isolated DB."""
    import app as app_module
    application = app_module.create_app()
    application.testing = True
    return application.test_client()


@pytest.fixture
def register(client):
    """Factory: register a user and return the parsed JSON response."""
    def _register(username="alice", password="password123", email=None):
        res = client.post("/api/auth/signup",
                          json={"username": username, "password": password, "email": email})
        return res
    return _register


@pytest.fixture
def auth_headers(client):
    """Factory: register (or reuse) a user and return Bearer auth headers."""
    def _headers(username="alice", password="password123"):
        res = client.post("/api/auth/signup",
                          json={"username": username, "password": password})
        if res.status_code == 409:
            res = client.post("/api/auth/login",
                             json={"username": username, "password": password})
        token = res.get_json()["token"]
        return {"Authorization": f"Bearer {token}"}
    return _headers
