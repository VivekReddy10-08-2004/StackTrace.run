"""Native auth: signup, login, /me, plus password-hash and JWT units (MEMO §2)."""

import auth


# --- health ---

def test_health_ok(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.get_json()
    assert body["status"] == "ok"
    assert body["database"].startswith("sqlite")


# --- signup ---

def test_signup_success(client):
    res = client.post("/api/auth/signup",
                     json={"username": "alice", "password": "password123", "email": "a@x.io"})
    assert res.status_code == 201
    body = res.get_json()
    assert body["token"]
    assert body["user"]["username"] == "alice"
    assert body["user"]["auth_provider"] == "native"
    assert body["profile"]["current_ranking"] == 1200
    assert body["profile"]["tickets_solved"] == 0


def test_signup_short_username(client):
    res = client.post("/api/auth/signup", json={"username": "ab", "password": "password123"})
    assert res.status_code == 400


def test_signup_short_password(client):
    res = client.post("/api/auth/signup", json={"username": "alice", "password": "short"})
    assert res.status_code == 400


def test_signup_duplicate_username(client):
    payload = {"username": "alice", "password": "password123"}
    assert client.post("/api/auth/signup", json=payload).status_code == 201
    res = client.post("/api/auth/signup", json=payload)
    assert res.status_code == 409


# --- login ---

def test_login_success(client, register):
    register("bob", "password123")
    res = client.post("/api/auth/login", json={"username": "bob", "password": "password123"})
    assert res.status_code == 200
    assert res.get_json()["token"]


def test_login_wrong_password(client, register):
    register("bob", "password123")
    res = client.post("/api/auth/login", json={"username": "bob", "password": "nope"})
    assert res.status_code == 401


def test_login_unknown_user(client):
    res = client.post("/api/auth/login", json={"username": "ghost", "password": "password123"})
    assert res.status_code == 401


# --- /me ---

def test_me_requires_token(client):
    assert client.get("/api/auth/me").status_code == 401


def test_me_with_bad_token(client):
    res = client.get("/api/auth/me", headers={"Authorization": "Bearer not.a.jwt"})
    assert res.status_code == 401


def test_me_with_valid_token(client, auth_headers):
    headers = auth_headers("carol")
    res = client.get("/api/auth/me", headers=headers)
    assert res.status_code == 200
    assert res.get_json()["user"]["username"] == "carol"


# --- password hashing (unit) ---

def test_password_hash_roundtrip():
    h = auth.hash_password("hunter2value")
    assert h != "hunter2value"          # never stored in plaintext
    assert h.startswith("$argon2")      # Argon2id
    assert auth.verify_password(h, "hunter2value")
    assert not auth.verify_password(h, "wrong")


def test_verify_rejects_empty_hash():
    assert not auth.verify_password(None, "whatever")
    assert not auth.verify_password("", "whatever")


# --- JWT (unit) ---

def test_jwt_roundtrip():
    token = auth.create_access_token("uid-1", "alice")
    payload = auth.decode_access_token(token)
    assert payload["sub"] == "uid-1"
    assert payload["username"] == "alice"


def test_jwt_expired_is_rejected(monkeypatch):
    import config
    monkeypatch.setattr(config.settings, "JWT_TTL_SECONDS", -5)  # already expired
    token = auth.create_access_token("uid-1", "alice")
    assert auth.decode_access_token(token) is None


def test_jwt_tampered_is_rejected():
    token = auth.create_access_token("uid-1", "alice")
    assert auth.decode_access_token(token + "x") is None
