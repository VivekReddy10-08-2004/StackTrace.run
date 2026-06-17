"""Award tracking, public profile, and leaderboard (MEMO §3)."""

import json

import users


# --- solve endpoint / award tracking ---

def test_solve_requires_auth(client):
    assert client.post("/api/profile/solve", json={"category": "Unix"}).status_code == 401


def test_solve_increments_stats(client, auth_headers):
    headers = auth_headers("dave")
    res = client.post("/api/profile/solve", headers=headers,
                     json={"category": "SQL", "difficulty": "hard"})
    assert res.status_code == 200
    body = res.get_json()
    assert body["profile"]["tickets_solved"] == 1
    assert body["profile"]["current_ranking"] == 1230   # 1200 + 30 (hard)
    assert body["profile"]["current_streak"] == 1
    assert "first_blood" in body["newly_earned"]


def test_elo_reward_by_difficulty(client, auth_headers):
    easy = auth_headers("easyuser")
    res = client.post("/api/profile/solve", headers=easy, json={"difficulty": "easy"})
    assert res.get_json()["profile"]["current_ranking"] == 1212   # +12

    med = auth_headers("meduser")
    res = client.post("/api/profile/solve", headers=med, json={"difficulty": "medium"})
    assert res.get_json()["profile"]["current_ranking"] == 1220   # +20


def test_unknown_difficulty_defaults_to_medium(client, auth_headers):
    headers = auth_headers("weird")
    res = client.post("/api/profile/solve", headers=headers, json={"difficulty": "spicy"})
    assert res.get_json()["profile"]["current_ranking"] == 1220   # default +20


def test_milestone_badges_unlock_progressively(client, auth_headers):
    headers = auth_headers("grinder")
    earned_overall = set()
    for i in range(5):
        body = client.post("/api/profile/solve", headers=headers,
                          json={"difficulty": "easy"}).get_json()
        earned_overall.update(body["newly_earned"])
    assert {"first_blood", "rookie"} <= earned_overall
    # 5 solves should NOT yet grant the 10-solve badge
    assert "on_call" not in earned_overall


def test_badge_not_awarded_twice(client, auth_headers):
    headers = auth_headers("repeat")
    first = client.post("/api/profile/solve", headers=headers, json={"difficulty": "easy"}).get_json()
    assert "first_blood" in first["newly_earned"]
    second = client.post("/api/profile/solve", headers=headers, json={"difficulty": "easy"}).get_json()
    assert "first_blood" not in second["newly_earned"]


# --- public profile ---

def test_public_profile_parses_badges(client, auth_headers):
    headers = auth_headers("erin")
    client.post("/api/profile/solve", headers=headers, json={"difficulty": "hard"})
    res = client.get("/api/profile/erin")
    assert res.status_code == 200
    body = res.get_json()
    assert isinstance(body["earned_badges"], list)      # parsed, not a JSON string
    assert "first_blood" in body["earned_badges"]
    assert body["tickets_solved"] == 1


def test_public_profile_404(client):
    assert client.get("/api/profile/nobody").status_code == 404


# --- leaderboard ---

def test_leaderboard_orders_by_elo(client, auth_headers):
    low = auth_headers("low")
    high = auth_headers("high")
    client.post("/api/profile/solve", headers=low, json={"difficulty": "easy"})    # +12
    for _ in range(3):
        client.post("/api/profile/solve", headers=high, json={"difficulty": "hard"})  # +90
    board = client.get("/api/leaderboard").get_json()["leaderboard"]
    names = [r["username"] for r in board]
    assert names.index("high") < names.index("low")
    assert board[0]["current_ranking"] >= board[1]["current_ranking"]


# --- service-level unit (no HTTP) ---

def test_record_solve_service(db_ready):
    user = users.create_native_user("svc", "hash", None)
    profile, newly = users.record_solve(user["user_id"], "Unix", "hard")
    assert profile["tickets_solved"] == 1
    assert profile["current_ranking"] == 1230
    assert "first_blood" in newly
    # earned_badges persisted as a JSON array string
    assert json.loads(profile["earned_badges"]) == ["first_blood"]
