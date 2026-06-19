"""
routes_admin.py — admin-only management endpoints.

Admins are designated by the ADMIN_USERNAMES env var (comma-separated). Every
route here requires a valid JWT whose username is in that list.
"""

from __future__ import annotations

from flask import Blueprint, g, jsonify

import users
from auth import admin_required

bp = Blueprint("admin", __name__, url_prefix="/api/admin")


@bp.get("/users")
@admin_required
def list_users():
    return jsonify({"users": users.list_all()})


@bp.delete("/users/<username>")
@admin_required
def delete_user(username):
    if username == g.user["username"]:
        return jsonify({"error": "you cannot delete your own account"}), 400
    if not users.delete_by_username(username):
        return jsonify({"error": "user not found"}), 404
    return jsonify({"deleted": username})
