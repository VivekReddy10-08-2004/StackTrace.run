"""
db.py — database access layer (MEMO 1.2 §1).

Two backends, chosen by DATABASE_URL:
  * Local dev  -> a SQLite file (stdlib sqlite3).
  * Production -> Turso (libSQL) over HTTPS via the pure-Python `libsql-client`.

We use libsql-client (not the Rust `libsql-experimental`) because it ships as a
pure-Python wheel that installs on modern Python where the Rust drivers don't.

There is intentionally **no silent fallback**: if DATABASE_URL points at Turso
but the client/token is missing, we raise loudly rather than quietly writing to
a local file you didn't mean to use.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from config import settings

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"

try:
    import libsql_client
    _HAS_LIBSQL_CLIENT = True
except ImportError:  # pragma: no cover
    _HAS_LIBSQL_CLIENT = False

_turso = None  # reused ClientSync (connection pooling for the HTTP client)


# --------------------------------------------------------------------------
# Backend selection
# --------------------------------------------------------------------------

def _on_turso() -> bool:
    return bool(settings.using_turso)


def backend_name() -> str:
    return "turso" if _on_turso() else "sqlite"


def _turso_client():
    global _turso
    if _turso is None:
        if not _HAS_LIBSQL_CLIENT:
            raise RuntimeError(
                "DATABASE_URL points at Turso but 'libsql-client' is not installed. "
                "Run: pip install libsql-client"
            )
        if not settings.TURSO_AUTH_TOKEN:
            raise RuntimeError(
                "DATABASE_URL points at Turso but TURSO_AUTH_TOKEN is not set in your .env."
            )
        # Use the HTTPS transport (robust, current). A libsql:// URL would make
        # the client use its websocket/hrana protocol, which is version-sensitive.
        url = settings.DATABASE_URL
        if url.startswith("libsql://"):
            url = "https://" + url[len("libsql://"):]
        _turso = libsql_client.create_client_sync(
            url=url, auth_token=settings.TURSO_AUTH_TOKEN
        )
    return _turso


def _sqlite():
    conn = sqlite3.connect(settings.LOCAL_SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


# --------------------------------------------------------------------------
# Schema bootstrap
# --------------------------------------------------------------------------

def init_db() -> str:
    """Create tables/indexes if absent. Returns the active backend name."""
    script = SCHEMA_PATH.read_text(encoding="utf-8")
    if _on_turso():
        client = _turso_client()
        for stmt in _split_statements(script):
            client.execute(stmt)
        return "turso"

    conn = _sqlite()
    try:
        conn.executescript(script)
        conn.commit()
    finally:
        conn.close()
    return "sqlite"


def _split_statements(script: str):
    return [s.strip() for s in script.split(";") if s.strip()]


# --------------------------------------------------------------------------
# Query helpers — uniform list-of-dict / dict results for both backends
# --------------------------------------------------------------------------

def query_one(sql: str, params: tuple = ()):
    rows = query_all(sql, params)
    return rows[0] if rows else None


def query_all(sql: str, params: tuple = ()):
    if _on_turso():
        rs = _turso_client().execute(sql, list(params))
        return [row.asdict() for row in rs.rows]
    conn = _sqlite()
    try:
        cur = conn.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def execute(sql: str, params: tuple = ()) -> None:
    if _on_turso():
        try:
            _turso_client().execute(sql, list(params))
        except Exception as e:  # noqa: BLE001
            # Normalise UNIQUE violations so callers can catch sqlite3.IntegrityError
            # regardless of backend (keeps the signup-duplicate 409 path working).
            msg = str(e)
            if "UNIQUE constraint" in msg or "SQLITE_CONSTRAINT" in msg:
                raise sqlite3.IntegrityError(msg) from e
            raise
        return

    conn = _sqlite()
    try:
        conn.execute(sql, params)
        conn.commit()
    finally:
        conn.close()
