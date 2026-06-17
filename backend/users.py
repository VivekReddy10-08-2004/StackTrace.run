"""
users.py — user identity + progression services (MEMO 1.2 §1 & §3).

Owns user creation (native + GitHub upsert), profile reads, and the award-tracking
logic that bumps Elo, streaks, and milestone badges when a ticket is solved.
"""

from __future__ import annotations

import json
import uuid

import db

# Elo reward per difficulty (simple K-factor model)
ELO_REWARD = {"easy": 12, "medium": 20, "hard": 30}

# Milestone badges keyed by tickets_solved threshold.
MILESTONES = [
    (1, "first_blood"),
    (5, "rookie"),
    (10, "on_call"),
    (25, "veteran"),
    (50, "incident_commander"),
]


# --------------------------------------------------------------------------
# Reads
# --------------------------------------------------------------------------

def get_user_by_username(username: str):
    return db.query_one("SELECT * FROM users WHERE username = ?", (username,))


def get_user_by_id(user_id: str):
    return db.query_one("SELECT * FROM users WHERE user_id = ?", (user_id,))


def get_user_by_email(email: str):
    if not email:
        return None
    return db.query_one("SELECT * FROM users WHERE email = ?", (email,))


def get_profile(user_id: str):
    return db.query_one("SELECT * FROM user_profiles WHERE user_id = ?", (user_id,))


def public_profile(username: str):
    """Joined, JSON-safe public view used by the API and OG sharing pages."""
    row = db.query_one(
        """
        SELECT u.username, u.auth_provider, u.created_at,
               p.current_ranking, p.tickets_solved, p.earned_badges, p.current_streak
        FROM users u JOIN user_profiles p ON u.user_id = p.user_id
        WHERE u.username = ?
        """,
        (username,),
    )
    if not row:
        return None
    row["earned_badges"] = json.loads(row.get("earned_badges") or "[]")
    return row


def leaderboard(limit: int = 20):
    rows = db.query_all(
        """
        SELECT u.username, p.current_ranking, p.tickets_solved
        FROM user_profiles p JOIN users u ON u.user_id = p.user_id
        ORDER BY p.current_ranking DESC
        LIMIT ?
        """,
        (limit,),
    )
    return rows


# --------------------------------------------------------------------------
# Writes
# --------------------------------------------------------------------------

def _create_profile(user_id: str):
    db.execute("INSERT INTO user_profiles (user_id) VALUES (?)", (user_id,))


def create_native_user(username: str, password_hash: str, email: str | None):
    user_id = uuid.uuid4().hex
    db.execute(
        """INSERT INTO users (user_id, username, email, password_hash, auth_provider)
           VALUES (?, ?, ?, ?, 'native')""",
        (user_id, username, email, password_hash),
    )
    _create_profile(user_id)
    return get_user_by_id(user_id)


def upsert_github_user(github_id: int, login: str, email: str | None):
    """Find-or-create a GitHub-authenticated user (MEMO §2, step 3)."""
    user_id = f"github:{github_id}"
    existing = get_user_by_id(user_id)
    if existing:
        return existing, False

    # avoid display-handle collisions with existing accounts
    username = login
    if get_user_by_username(username):
        username = f"{login}-{github_id}"

    db.execute(
        """INSERT INTO users (user_id, username, email, password_hash, auth_provider)
           VALUES (?, ?, ?, NULL, 'github')""",
        (user_id, username, email),
    )
    _create_profile(user_id)
    return get_user_by_id(user_id), True


def record_solve(user_id: str, category: str, difficulty: str):
    """
    Award-tracking core (MEMO §3): on a solved ticket, bump tickets_solved,
    grant Elo, advance the streak, and unlock any newly-earned milestone badges.
    Returns (updated_profile_dict, newly_earned_badges_list).
    """
    profile = get_profile(user_id)
    if not profile:
        _create_profile(user_id)
        profile = get_profile(user_id)

    solved = (profile["tickets_solved"] or 0) + 1
    ranking = (profile["current_ranking"] or 1200) + ELO_REWARD.get((difficulty or "").lower(), 20)
    streak = (profile["current_streak"] or 0) + 1

    earned = set(json.loads(profile.get("earned_badges") or "[]"))
    newly = [tag for threshold, tag in MILESTONES if solved >= threshold and tag not in earned]
    earned.update(newly)

    db.execute(
        """UPDATE user_profiles
           SET tickets_solved = ?, current_ranking = ?, current_streak = ?,
               earned_badges = ?, last_solved_at = CURRENT_TIMESTAMP
           WHERE user_id = ?""",
        (solved, ranking, streak, json.dumps(sorted(earned)), user_id),
    )
    return get_profile(user_id), newly
