"""
config.py — environment configuration for the StackTrace.run backend (MEMO 1.2).

Free-tier checklist (§4) is enforced here:
  * DATABASE_URL is honoured, with a local SQLite fallback to preserve free-tier
    Turso bandwidth/space.
  * GitHub OAuth creds come from env so dev and prod apps stay separate.
  * CORS origins are an explicit allow-list, not a wildcard.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path

from dotenv import dotenv_values

BACKEND_DIR = Path(__file__).resolve().parent
ROOT_DIR = BACKEND_DIR.parent


def _load_env() -> dict:
    values = {}
    # root project.env first, then backend/.env (backend wins), then real env.
    for f in (ROOT_DIR / "project.env", BACKEND_DIR / ".env"):
        if f.exists():
            values.update(dotenv_values(f))
    values.update(os.environ)
    return values


_ENV = _load_env()


def _get(name: str, default=None):
    val = _ENV.get(name)
    return val if val not in (None, "") else default


class Settings:
    # --- Database (§1) ---
    # e.g. libsql://your-db.turso.io  (prod)  |  unset -> local SQLite (dev)
    DATABASE_URL: str | None = _get("DATABASE_URL")
    TURSO_AUTH_TOKEN: str | None = _get("TURSO_AUTH_TOKEN")
    LOCAL_SQLITE_PATH: str = _get("LOCAL_SQLITE_PATH", str(BACKEND_DIR / "local_dev.db"))

    # --- Auth / JWT (§2) ---
    JWT_SECRET: str = _get("JWT_SECRET") or secrets.token_hex(32)
    JWT_ALGORITHM: str = "HS256"
    JWT_TTL_SECONDS: int = int(_get("JWT_TTL_SECONDS", "3600"))  # short-lived
    JWT_SECRET_IS_EPHEMERAL: bool = _get("JWT_SECRET") is None

    # --- GitHub OAuth (§2) ---
    GITHUB_CLIENT_ID: str | None = _get("GITHUB_CLIENT_ID")
    GITHUB_CLIENT_SECRET: str | None = _get("GITHUB_CLIENT_SECRET")
    GITHUB_REDIRECT_URI: str = _get(
        "GITHUB_REDIRECT_URI", "http://localhost:8000/api/auth/github/callback"
    )

    # --- Frontend / sharing (§3) ---
    FRONTEND_URL: str = _get("FRONTEND_URL", "http://localhost:4321")
    PUBLIC_BASE_URL: str = _get("PUBLIC_BASE_URL", "http://localhost:8000")

    # --- CORS (§4) ---
    CORS_ORIGINS: list[str] = [
        o.strip() for o in _get(
            "CORS_ORIGINS",
            "http://localhost:4321,http://127.0.0.1:4321",
        ).split(",") if o.strip()
    ]

    @property
    def using_turso(self) -> bool:
        return bool(self.DATABASE_URL and self.DATABASE_URL.startswith(("libsql://", "https://")))


settings = Settings()
