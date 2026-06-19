"""
app.py — StackTrace.run backend entry point (MEMO 1.2).

Wires the auth + profile blueprints, an explicit CORS allow-list (§4), and
database bootstrap. Run with:  python app.py   (dev)  or via a WSGI server (prod).
"""

from __future__ import annotations

import sys

from flask import Flask, jsonify
from flask_cors import CORS

import db
from config import settings
from routes_admin import bp as admin_bp
from routes_auth import bp as auth_bp
from routes_profile import bp as profile_bp


def create_app() -> Flask:
    app = Flask(__name__)

    # §4: explicit origin allow-list, not a wildcard.
    CORS(app, resources={r"/api/*": {"origins": settings.CORS_ORIGINS}},
         supports_credentials=True)

    backend = db.init_db()
    app.logger.info("Database ready (%s)", backend)
    if settings.JWT_SECRET_IS_EPHEMERAL:
        app.logger.warning("JWT_SECRET not set — using an ephemeral dev secret. "
                           "Tokens will not survive a restart. Set JWT_SECRET in prod.")

    app.register_blueprint(auth_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(admin_bp)

    @app.get("/api/health")
    def health():
        return jsonify({
            "status": "ok",
            "database": "turso" if settings.using_turso else "sqlite (local)",
            "github_oauth": bool(settings.GITHUB_CLIENT_ID),
        })

    @app.get("/")
    def index():
        # Landing page so the Space root isn't a bare 404. This image is the
        # API engine; the playable frontend is hosted separately.
        return (
            """<!doctype html><html><head><meta charset="utf-8">
            <title>StackTrace.run — API Engine</title>
            <style>body{background:#0c0f14;color:#d6dbe2;font-family:system-ui,sans-serif;
            display:flex;min-height:100vh;align-items:center;justify-content:center;margin:0}
            .c{max-width:560px;padding:32px}h1{color:#5a9d78;margin:0 0 8px}
            code{background:#191e26;padding:2px 6px;border-radius:4px}a{color:#6f97c0}</style></head>
            <body><div class="c"><h1>StackTrace.run — API Engine</h1>
            <p>This is the backend API for the StackTrace.run DevOps incident simulator.
            The playable frontend is hosted separately.</p>
            <p>Health: <a href="/api/health">/api/health</a> ·
            Leaderboard: <a href="/api/leaderboard">/api/leaderboard</a></p>
            <p style="color:#8a93a0;font-size:13px">POST <code>/api/auth/signup</code>,
            <code>/api/auth/login</code>, <code>/api/profile/solve</code> … see the repo README.</p>
            </div></body></html>""",
            200,
            {"Content-Type": "text/html"},
        )

    return app


app = create_app()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    # use_reloader=False: Werkzeug's auto-reloader crashes on Windows (WinError 10038)
    # when files change while running. Restart manually after code edits instead.
    app.run(host="127.0.0.1", port=port, debug=True, use_reloader=False)
