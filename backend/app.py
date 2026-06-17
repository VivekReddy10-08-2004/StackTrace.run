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

    @app.get("/api/health")
    def health():
        return jsonify({
            "status": "ok",
            "database": "turso" if settings.using_turso else "sqlite (local)",
            "github_oauth": bool(settings.GITHUB_CLIENT_ID),
        })

    return app


app = create_app()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    # use_reloader=False: Werkzeug's auto-reloader crashes on Windows (WinError 10038)
    # when files change while running. Restart manually after code edits instead.
    app.run(host="127.0.0.1", port=port, debug=True, use_reloader=False)
