"""
routes_auth.py — unified login / sign-up entry points (MEMO 1.2 §2).

Native credential auth (Argon2id + JWT) and the GitHub OAuth handshake share this
blueprint so the frontend has a single, consistent auth surface.
"""

from __future__ import annotations

import secrets
import sqlite3
from urllib.parse import urlencode

import httpx
from flask import Blueprint, g, jsonify, redirect, request

import users
from auth import (create_access_token, hash_password, is_admin, login_required,
                  verify_password)
from config import settings

bp = Blueprint("auth", __name__, url_prefix="/api/auth")

GITHUB_AUTHORIZE = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN = "https://github.com/login/oauth/access_token"
GITHUB_USER = "https://api.github.com/user"
GITHUB_EMAILS = "https://api.github.com/user/emails"

# In-memory CSRF state store for the OAuth round-trip (swap for Redis in prod).
_oauth_states: set[str] = set()


def _profile_payload(user):
    profile = users.get_profile(user["user_id"])
    return {
        "user": {
            "user_id": user["user_id"],
            "username": user["username"],
            "email": user.get("email"),
            "auth_provider": user["auth_provider"],
            "is_admin": is_admin(user["username"]),
        },
        "profile": profile,
    }


# --------------------------------------------------------------------------
# Native auth
# --------------------------------------------------------------------------

@bp.post("/signup")
def signup():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    email = (data.get("email") or "").strip() or None

    if len(username) < 3:
        return jsonify({"error": "username must be at least 3 characters"}), 400
    if len(password) < 8:
        return jsonify({"error": "password must be at least 8 characters"}), 400

    # Pre-check uniqueness so we return a clean 409 on every backend. (The Turso
    # HTTP client doesn't surface DB constraint errors catchably, so we can't rely
    # solely on the UNIQUE constraint raising.)
    if users.get_user_by_username(username) or users.get_user_by_email(email):
        return jsonify({"error": "username or email already taken"}), 409

    try:
        user = users.create_native_user(username, hash_password(password), email)
    except sqlite3.IntegrityError:
        return jsonify({"error": "username or email already taken"}), 409

    token = create_access_token(user["user_id"], user["username"])
    return jsonify({"token": token, **_profile_payload(user)}), 201


@bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    user = users.get_user_by_username(username)
    if not user or not verify_password(user.get("password_hash"), password):
        return jsonify({"error": "invalid username or password"}), 401

    token = create_access_token(user["user_id"], user["username"])
    return jsonify({"token": token, **_profile_payload(user)})


@bp.get("/me")
@login_required
def me():
    user = users.get_user_by_id(g.user["user_id"])
    if not user:
        return jsonify({"error": "user not found"}), 404
    return jsonify(_profile_payload(user))


# --------------------------------------------------------------------------
# GitHub OAuth (MEMO §2, steps 1-3)
# --------------------------------------------------------------------------

@bp.get("/github/login")
def github_login():
    if not settings.GITHUB_CLIENT_ID:
        return jsonify({"error": "GitHub OAuth is not configured (set GITHUB_CLIENT_ID)"}), 503
    state = secrets.token_urlsafe(16)
    _oauth_states.add(state)
    params = {
        "client_id": settings.GITHUB_CLIENT_ID,
        "redirect_uri": settings.GITHUB_REDIRECT_URI,
        "scope": "read:user user:email",
        "state": state,
    }
    return redirect(f"{GITHUB_AUTHORIZE}?{urlencode(params)}")


@bp.get("/github/callback")
def github_callback():
    if not (settings.GITHUB_CLIENT_ID and settings.GITHUB_CLIENT_SECRET):
        return jsonify({"error": "GitHub OAuth is not configured"}), 503

    code = request.args.get("code")
    state = request.args.get("state")
    if not code or state not in _oauth_states:
        return jsonify({"error": "invalid OAuth state or code"}), 400
    _oauth_states.discard(state)

    with httpx.Client(timeout=15) as client:
        # Step 2: exchange the code for an access token (backend-to-backend).
        token_res = client.post(
            GITHUB_TOKEN,
            headers={"Accept": "application/json"},
            data={
                "client_id": settings.GITHUB_CLIENT_ID,
                "client_secret": settings.GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": settings.GITHUB_REDIRECT_URI,
            },
        )
        access_token = token_res.json().get("access_token")
        if not access_token:
            return jsonify({"error": "failed to obtain GitHub access token"}), 400

        # Step 3: fetch the profile + primary email.
        gh_headers = {"Authorization": f"Bearer {access_token}",
                      "Accept": "application/vnd.github+json"}
        gh_user = client.get(GITHUB_USER, headers=gh_headers).json()
        email = gh_user.get("email")
        if not email:
            emails = client.get(GITHUB_EMAILS, headers=gh_headers).json()
            primary = next((e for e in emails if e.get("primary")), None) if isinstance(emails, list) else None
            email = primary["email"] if primary else None

    user, _created = users.upsert_github_user(
        github_id=gh_user["id"], login=gh_user["login"], email=email
    )
    token = create_access_token(user["user_id"], user["username"])

    # Hand the JWT back to the frontend (it persists it for session state).
    return redirect(f"{settings.FRONTEND_URL}/?token={token}")
