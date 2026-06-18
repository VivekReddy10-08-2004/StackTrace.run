# StackTrace.run Backend (MEMO 1.2)

---
title: StackTrace API Engine
emoji: 🛠️
colorFrom: blue
colorTo: slate
sdk: docker
app_port: 7860
pinned: false
---

# StackTrace.run Core Orchestrator API Backend
This space runs the automated Stack Overflow processing pipeline and user state state machine.

Python/Flask backend implementing **Authentication, Database Setup, and Achievement
Sharing** for DEV-SIM. Free-tier friendly: runs on local SQLite in dev, Turso
(libSQL) in prod.

## Quick start

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env        # optional in dev; fill JWT_SECRET + GitHub creds for prod
python app.py               # serves http://127.0.0.1:8000  (or: python app.py 8000)
```

Health check: `GET /api/health`.

## Layout

| File | Responsibility |
|------|----------------|
| `app.py` | Flask app factory, CORS allow-list, DB bootstrap, `/api/health` |
| `config.py` | Env config (DATABASE_URL, JWT, GitHub, CORS) with dev defaults |
| `db.py` | DB layer — Turso (libSQL) in prod, **local SQLite fallback** in dev |
| `schema.sql` | `users` + `user_profiles` + leaderboard index (memo §1) |
| `auth.py` | Argon2id hashing, JWT issue/verify, `@login_required` |
| `users.py` | User create/upsert + award-tracking (Elo, streak, badges) |
| `routes_auth.py` | `/api/auth/*` — native signup/login + GitHub OAuth |
| `routes_profile.py` | award tracking, public profile, leaderboard, OG share page + image |

## Endpoints

**Auth (§2)**
- `POST /api/auth/signup` `{username, password, email?}` → `{token, user, profile}`
- `POST /api/auth/login` `{username, password}` → `{token, user, profile}`
- `GET  /api/auth/me` *(Bearer JWT)* → current user + profile
- `GET  /api/auth/github/login` → redirect to GitHub authorize
- `GET  /api/auth/github/callback` → exchange code, upsert user, redirect to frontend with `?token=`

**Progression & sharing (§3)**
- `POST /api/profile/solve` *(Bearer JWT)* `{category, difficulty}` → updated profile + newly-earned badges
- `GET  /api/profile/<username>` → public JSON profile
- `GET  /api/leaderboard` → top players by Elo
- `GET  /user/<username>` → public HTML page with **dynamic OpenGraph tags**
- `GET  /api/og-image?user=&rank=&solved=&badge=` → achievement card (SVG)

## Achievement image: dev vs prod

- **Dev/local:** `GET /api/og-image` returns an SVG card (zero dependencies).
- **Prod (memo's strategy):** deploy `../api/og-image.js` (Vercel Edge + `@vercel/og`)
  which renders a PNG on-the-fly. Point `og:image` at that function in production.

## Tests & seed data

```bash
pip install -r requirements-dev.txt
python -m pytest            # 35 tests; each uses an isolated temp SQLite DB
```

Coverage: native auth (signup/login/me, validation, 409/401), Argon2 hashing,
JWT (roundtrip/expiry/tamper), award tracking (Elo by difficulty, streaks,
milestone badges), public profile + leaderboard, OG share page + image (incl.
param escaping), and the GitHub OAuth handshake (login redirect, CSRF state,
mocked callback upsert, idempotency).

Populate demo players for manual dashboard/leaderboard testing:

```bash
python seed.py             # idempotent; adds 5 demo users (password: password123)
python seed.py --reset     # wipe users/profiles first
```

## §4 — Free-tier configuration checklist

- [x] **DATABASE_URL with local SQLite fallback** — `db.py` uses Turso only when
  `DATABASE_URL` is a `libsql://` URL *and* the driver is installed; otherwise it
  writes to `backend/local_dev.db`, preserving free-tier Turso quota.
- [x] **Separate dev/prod GitHub OAuth apps** — creds come from env
  (`GITHUB_CLIENT_ID/SECRET`, `GITHUB_REDIRECT_URI`); register one app per
  environment at <https://github.com/settings/developers>.
- [x] **Explicit CORS allow-list** — `CORS_ORIGINS` (no wildcard); defaults to the
  local frontend, add your Vercel staging/prod domains in `.env`.

## Notes / next steps

- Set a stable `JWT_SECRET` in production (dev uses an ephemeral one).
- To enable Turso: set `DATABASE_URL`/`TURSO_AUTH_TOKEN` and uncomment
  `libsql-experimental` in `requirements.txt`.
- Frontend wiring (login UI + calling `/api/profile/solve` on ticket resolve) is
  the next increment — the API surface is ready for it.
