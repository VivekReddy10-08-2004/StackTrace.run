"""
seed.py — populate the local database with demo players so the dashboard and
leaderboard look alive during manual testing.

    python seed.py            # add demo users (idempotent)
    python seed.py --reset    # wipe users/profiles first, then seed

All demo accounts use the password:  password123
"""

from __future__ import annotations

import json
import sys

# Windows consoles default to cp1252 and choke on ✓/· glyphs.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

import db
import users
from auth import hash_password

# (username, email, ranking, tickets_solved, streak, badges)
DEMO_PLAYERS = [
    ("grace_hopper", "grace@stacktrace.run", 1820, 73, 9,
     ["first_blood", "rookie", "on_call", "veteran", "incident_commander"]),
    ("ada_lovelace", "ada@stacktrace.run", 1540, 38, 4,
     ["first_blood", "rookie", "on_call", "veteran"]),
    ("linus_t", "linus@stacktrace.run", 1390, 21, 2,
     ["first_blood", "rookie", "on_call"]),
    ("ken_thompson", "ken@stacktrace.run", 1265, 9, 1,
     ["first_blood", "rookie"]),
    ("newbie_sam", "sam@stacktrace.run", 1212, 1, 1,
     ["first_blood"]),
]


def reset():
    db.execute("DELETE FROM user_profiles")
    db.execute("DELETE FROM users")
    print("· cleared users + profiles")


def seed():
    created = 0
    for username, email, ranking, solved, streak, badges in DEMO_PLAYERS:
        if users.get_user_by_username(username):
            print(f"· {username} already exists — skipping")
            continue
        user = users.create_native_user(username, hash_password("password123"), email)
        db.execute(
            """UPDATE user_profiles
               SET current_ranking = ?, tickets_solved = ?, current_streak = ?, earned_badges = ?
               WHERE user_id = ?""",
            (ranking, solved, streak, json.dumps(badges), user["user_id"]),
        )
        created += 1
        print(f"✓ seeded {username}  ({ranking} Elo, {solved} solved)")
    print(f"\nDone. {created} new demo player(s). Password for all: password123")


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    backend = db.init_db()
    print(f"Seeding database ({backend})…")
    if "--reset" in argv:
        reset()
    seed()


if __name__ == "__main__":
    main()
