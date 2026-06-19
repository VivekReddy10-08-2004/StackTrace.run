"""
auth.py — password hashing + JWT session tokens (MEMO 1.2 §2).

Passwords are transformed with Argon2id (non-reversible) before storage. Sessions
are short-lived HS256 JWTs the frontend holds for state persistence.
"""

from __future__ import annotations

import time
from functools import wraps

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
from flask import g, jsonify, request

from config import settings

_ph = PasswordHasher()  # Argon2id with sane defaults


# --- password hashing ---

def hash_password(plaintext: str) -> str:
    return _ph.hash(plaintext)


def verify_password(stored_hash: str, plaintext: str) -> bool:
    if not stored_hash:
        return False
    try:
        return _ph.verify(stored_hash, plaintext)
    except (VerifyMismatchError, InvalidHashError):
        return False


# --- JWT ---

def create_access_token(user_id: str, username: str) -> str:
    now = int(time.time())
    payload = {
        "sub": user_id,
        "username": username,
        "iat": now,
        "exp": now + settings.JWT_TTL_SECONDS,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None


def _bearer_token() -> str | None:
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[7:].strip()
    return None


def login_required(view):
    """Route decorator: requires a valid bearer JWT, populates flask.g.user."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        token = _bearer_token()
        payload = decode_access_token(token) if token else None
        if not payload:
            return jsonify({"error": "authentication required"}), 401
        g.user = {"user_id": payload["sub"], "username": payload.get("username")}
        return view(*args, **kwargs)

    return wrapper


def is_admin(username: str | None) -> bool:
    return bool(username) and username in settings.ADMIN_USERNAMES


def admin_required(view):
    """Route decorator: requires a valid JWT whose user is an admin."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        token = _bearer_token()
        payload = decode_access_token(token) if token else None
        if not payload:
            return jsonify({"error": "authentication required"}), 401
        if not is_admin(payload.get("username")):
            return jsonify({"error": "admin access required"}), 403
        g.user = {"user_id": payload["sub"], "username": payload.get("username")}
        return view(*args, **kwargs)

    return wrapper
