# StackTrace.run

---
title: StackTrace API Engine
sdk: docker
app_port: 7860
---
---
> A browser-based DevOps incident simulator. Play a junior on-call engineer fixing broken servers, scripts, and databases inside a fake terminal — earn an Elo rank, streaks, and badges, and share a live profile card.

![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB)
![Flask](https://img.shields.io/badge/Flask-API-000000)
![Frontend](https://img.shields.io/badge/Frontend-Vanilla%20JS-F7DF1E)
![Database](https://img.shields.io/badge/DB-Turso%20%2F%20SQLite-4FF8D2)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED)
![Tests](https://img.shields.io/badge/tests-35%20passing-brightgreen)

---

## What it is

Players receive **incident tickets** (a disk filling up, a crashing Python backup script, a locked-out database account) and resolve them in an in-browser mock Unix terminal — navigating a virtual file system, editing files in a fake `nano`, and running **real SQL** against an in-browser SQLite engine. Accounts track progression; levels can be **hand-authored** or **auto-generated from real Stack Overflow threads** by an LLM.

**Highlights**
- 🖥️ **Mock terminal** with a virtual file system, command history, and a `nano`-style editor — no real OS is ever touched.
- 🗄️ **Real SQL in the browser** via `sql.js` (SQLite compiled to WebAssembly).
- 🔐 **Accounts**: native sign-up (Argon2id + JWT) and **GitHub OAuth**.
- 🏆 **Progression**: Elo ranking, streaks, milestone badges, and a leaderboard.
- 🔗 **Shareable profile cards** via dynamic OpenGraph meta tags + an on-the-fly image.
- 🤖 **AI content pipeline**: turn Stack Overflow Q&A into playable levels (with difficulty scaling).
- ✅ **35 automated tests** and a Docker-based deploy path.

---

## Architecture

Three cooperating pieces, plus an offline content pipeline:

```
  ┌────────────────────┐     HTTP / JSON      ┌────────────────────┐     libSQL      ┌──────────────┐
  │  FRONTEND          │ ───────────────────▶ │  BACKEND           │ ──────────────▶ │  DATABASE    │
  │  HTML · CSS · JS   │ ◀─────────────────── │  Python · Flask    │ ◀────────────── │ Turso/SQLite │
  │  (browser, :4321)  │                      │  (:8000)           │                 └──────────────┘
  └────────────────────┘                      └────────────────────┘

  ┌─────────────────────────────────────────────────────────────────────────────────────┐
  │  CONTENT PIPELINE (run by hand)                                                        │
  │  generate_level.py → Stack Overflow API → prune → LLM (Groq) → src/levels/*.json       │
  └─────────────────────────────────────────────────────────────────────────────────────┘
```

The frontend and backend run on **separate ports** (the frontend calls the backend over HTTP). With `DATABASE_URL` set, the backend uses **Turso (libSQL)**; unset, it falls back to a **local SQLite** file.

---

## Tech stack

| Layer | Choices |
|---|---|
| **Frontend** | Vanilla HTML5 / CSS3 / JavaScript (no build step), `sql.js` (SQLite/WASM) |
| **Backend** | Python · Flask · Flask-CORS · PyJWT · argon2-cffi · httpx |
| **Database** | Turso (libSQL) in prod · SQLite locally · accessed via `libsql-client` |
| **Auth** | Argon2id password hashing · JWT sessions · GitHub OAuth |
| **Content AI** | Stack Exchange API + Groq LLM (`llama-3.3-70b`) |
| **Tooling** | pytest · Docker · waitress (prod WSGI) |

---

## Repository structure

```
.
├── index.html              Frontend entry: 3 views (login · dashboard · game)
├── css/styles.css          Dark, professional theme (design tokens)
├── js/
│   ├── filesystem.js       Virtual Unix file system (tree)
│   ├── levels.js           Built-in levels (data + win checks)
│   ├── generated-levels.js Loads AI-generated levels
│   ├── terminal.js         Terminal widget (I/O, history)
│   ├── game.js             Game engine (state machine, commands, timer, scoring)
│   ├── auth.js             Login/signup, JWT storage, backend calls
│   └── app.js              View router (which screen shows when)
│
├── backend/                Flask API (accounts, progression, sharing)
│   ├── app.py              App factory + server entry
│   ├── config.py           Env/config + secrets loading
│   ├── db.py               DB layer (Turso / SQLite)
│   ├── schema.sql          users + user_profiles tables
│   ├── auth.py             Argon2 hashing + JWT
│   ├── users.py            User + progression logic
│   ├── routes_auth.py      /api/auth/* (incl. GitHub OAuth)
│   ├── routes_profile.py   scores, leaderboard, OG share page + image
│   ├── seed.py             Insert demo players
│   ├── tests/              pytest suite (35 tests)
│   └── Dockerfile          Production backend image
│
├── generate_level.py       Content pipeline: Stack Overflow + LLM → level JSON
├── src/levels/             Generated levels + manifest.json
├── api/og-image.js         Production share-image function (Vercel)
└── docker-compose.yml      One-command local stack
```

---

## Quick start

You need the backend on **:8000** and the frontend on **:4321** (different ports — the frontend's API base is `:8000`).

### Option A — Docker (recommended)

```bash
docker compose up --build
```

- Backend → http://localhost:8000
- Frontend → http://localhost:4321

Config/secrets are read from your git-ignored env files (see [Configuration](#configuration)).

### Option B — Run locally (two terminals)

```bash
# Terminal 1 — backend
cd backend
pip install -r requirements.txt
python app.py                 # http://127.0.0.1:8000

# Terminal 2 — frontend (any port except 8000)
python -m http.server 4321    # http://localhost:4321
```

Then open **http://localhost:4321**. Optionally seed demo players first: `python backend/seed.py`.

> Serve over HTTP, not `file://` — `sql.js` and the backend calls require it.

---

## How it works

- **Frontend** (`js/`) is event-driven vanilla JS. `game.js` is a state machine that loads a ticket, sets up the virtual file system (and an `sql.js` database for SQL levels), parses typed commands, runs a 5-minute "uptime" timer, and checks win conditions. `auth.js` handles login and syncs solved tickets to the backend; `app.js` gates the three screens.
- **Backend** (`backend/`) is a Flask REST API. It hashes passwords (Argon2id), issues JWTs, supports GitHub OAuth, records Elo/streak/badges on each solve, and serves a public profile page with dynamic OpenGraph tags + an OG image.
- **Content pipeline** (`generate_level.py`) fetches a highly-rated Stack Overflow thread, prunes it, and asks an LLM to convert it into a strict level JSON (broken files + a win condition), optionally scaling difficulty.

---

## Backend API

| Method · Path | Purpose |
|---|---|
| `GET /api/health` | Service + database status |
| `POST /api/auth/signup` | Create an account |
| `POST /api/auth/login` | Log in (returns a JWT) |
| `GET /api/auth/me` | Current user + profile *(auth)* |
| `GET /api/auth/github/login` · `…/callback` | GitHub OAuth flow |
| `POST /api/profile/solve` | Record a solved ticket *(auth)* |
| `GET /api/profile/<username>` | Public profile JSON |
| `GET /api/leaderboard` | Top players by Elo |
| `GET /user/<username>` | Public share page (OpenGraph tags) |
| `GET /api/og-image` | Dynamic achievement card (SVG) |

---

## Generating levels

```bash
pip install -r requirements.txt
python generate_level.py --count 3            # one per DevOps tag
python generate_level.py --difficulty easy    # scale a problem down
python generate_level.py --offline            # exercise the pipeline, no network
```

Outputs land in `src/levels/` as `level_N.json` + a `manifest.json` index. Play them via the **"Stack Overflow sourced"** toggle on the dashboard. (Requires `STACK_API_KEY` and `Groq_API_key`.)

---

## Testing

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest          # 35 tests, isolated temp SQLite per test
```

Covers native auth, hashing/JWT, award tracking, public profile/leaderboard, the OG share page/image, and the GitHub OAuth handshake (GitHub calls mocked — no network needed).

---

## Configuration

Settings come from env vars (locally via git-ignored `backend/.env` / `project.env`; in Docker via `env_file`). Secrets are **never** committed or baked into images.

| Variable | Used by | Notes |
|---|---|---|
| `DATABASE_URL` | backend | `libsql://…turso.io` for Turso; unset → local SQLite |
| `TURSO_AUTH_TOKEN` | backend | required when `DATABASE_URL` is a Turso URL |
| `JWT_SECRET` | backend | signing key for sessions (set a stable one in prod) |
| `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` | backend | enable GitHub OAuth |
| `CORS_ORIGINS` | backend | allow-list of frontend origins |
| `STACK_API_KEY` / `Groq_API_key` | generator | for `generate_level.py` |

---

## Deployment notes

- **Backend** → ship the `backend/Dockerfile` image (Python 3.12 + waitress) to any container host (Render, Railway, Fly.io, a VPS). Inject env vars at runtime.
- **Frontend** → static files; host on a CDN/static host (Vercel, Netlify, Cloudflare Pages).
- **Database** → Turso (free tier) for production; SQLite for local dev.
- **Before deploying**, make the frontend's API base configurable — it currently hard-codes `http://<host>:8000`, which assumes backend and frontend share a host.

---

## Status

Active prototype. Core game loop, accounts/progression, sharing, the AI content pipeline, and a Turso-backed deployment path are all in place and tested.
