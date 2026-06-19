"""Admin endpoints — admins are designated by ADMIN_USERNAMES."""

import config


def test_admin_requires_auth(client):
    assert client.get("/api/admin/users").status_code == 401


def test_non_admin_is_forbidden(client, auth_headers):
    headers = auth_headers("normaluser")
    assert client.get("/api/admin/users", headers=headers).status_code == 403


def test_me_reports_admin_flag(client, auth_headers, monkeypatch):
    monkeypatch.setattr(config.settings, "ADMIN_USERNAMES", ["boss"])
    headers = auth_headers("boss")
    body = client.get("/api/auth/me", headers=headers).get_json()
    assert body["user"]["is_admin"] is True


def test_admin_can_list_and_delete_users(client, auth_headers, monkeypatch):
    monkeypatch.setattr(config.settings, "ADMIN_USERNAMES", ["boss"])
    admin = auth_headers("boss")
    auth_headers("victim")

    listed = client.get("/api/admin/users", headers=admin)
    assert listed.status_code == 200
    names = [u["username"] for u in listed.get_json()["users"]]
    assert {"boss", "victim"} <= set(names)

    gone = client.delete("/api/admin/users/victim", headers=admin)
    assert gone.status_code == 200
    assert client.get("/api/profile/victim").status_code == 404


def test_admin_cannot_delete_self(client, auth_headers, monkeypatch):
    monkeypatch.setattr(config.settings, "ADMIN_USERNAMES", ["boss"])
    admin = auth_headers("boss")
    assert client.delete("/api/admin/users/boss", headers=admin).status_code == 400


def test_delete_unknown_user_404(client, auth_headers, monkeypatch):
    monkeypatch.setattr(config.settings, "ADMIN_USERNAMES", ["boss"])
    admin = auth_headers("boss")
    assert client.delete("/api/admin/users/ghost", headers=admin).status_code == 404
