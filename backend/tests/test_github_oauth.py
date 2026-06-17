"""GitHub OAuth handshake (MEMO §2). GitHub HTTP calls are mocked."""

from urllib.parse import parse_qs, urlparse

import pytest

import config
import routes_auth


# --- fake httpx client standing in for GitHub ---

class _FakeResp:
    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data


class _FakeClient:
    """Mimics httpx.Client used inside the callback handler."""
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def post(self, url, **kwargs):           # token exchange
        return _FakeResp({"access_token": "gho_testtoken"})

    def get(self, url, **kwargs):            # profile / emails
        if url.endswith("/user"):
            return _FakeResp({"id": 424242, "login": "octocat", "email": "octo@cat.io"})
        return _FakeResp([{"email": "octo@cat.io", "primary": True}])


@pytest.fixture
def github_configured(monkeypatch):
    monkeypatch.setattr(config.settings, "GITHUB_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(config.settings, "GITHUB_CLIENT_SECRET", "test-client-secret")


# --- login redirect ---

def test_github_login_disabled_without_creds(client):
    # default .env leaves the creds blank
    assert client.get("/api/auth/github/login").status_code == 503


def test_github_login_redirects_to_github(client, github_configured):
    res = client.get("/api/auth/github/login")
    assert res.status_code == 302
    loc = res.headers["Location"]
    assert loc.startswith("https://github.com/login/oauth/authorize")
    q = parse_qs(urlparse(loc).query)
    assert q["client_id"] == ["test-client-id"]
    assert "state" in q


# --- callback ---

def test_github_callback_rejects_bad_state(client, github_configured):
    res = client.get("/api/auth/github/callback?code=abc&state=forged")
    assert res.status_code == 400


def test_github_callback_creates_user_and_returns_token(client, github_configured, monkeypatch):
    monkeypatch.setattr(routes_auth.httpx, "Client", _FakeClient)

    # 1. begin the flow so a valid CSRF state is registered
    login = client.get("/api/auth/github/login")
    state = parse_qs(urlparse(login.headers["Location"]).query)["state"][0]

    # 2. GitHub redirects back with code + state
    res = client.get(f"/api/auth/github/callback?code=realcode&state={state}")
    assert res.status_code == 302
    assert res.headers["Location"].startswith(config.settings.FRONTEND_URL)
    assert "token=" in res.headers["Location"]

    # 3. the GitHub user now exists with a public profile
    prof = client.get("/api/profile/octocat")
    assert prof.status_code == 200
    assert prof.get_json()["auth_provider"] == "github"


def test_github_callback_is_idempotent(client, github_configured, monkeypatch):
    monkeypatch.setattr(routes_auth.httpx, "Client", _FakeClient)

    def run_once():
        login = client.get("/api/auth/github/login")
        state = parse_qs(urlparse(login.headers["Location"]).query)["state"][0]
        return client.get(f"/api/auth/github/callback?code=c&state={state}")

    assert run_once().status_code == 302
    assert run_once().status_code == 302   # second login must not error/duplicate
    # still exactly one octocat on the leaderboard
    board = client.get("/api/leaderboard").get_json()["leaderboard"]
    assert sum(1 for r in board if r["username"] == "octocat") == 1
