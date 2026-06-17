"""
routes_profile.py — award tracking + dynamic achievement sharing (MEMO 1.2 §3).

  * POST /api/profile/solve   — record a solved ticket (Elo / streak / badges)
  * GET  /api/profile/<user>  — public JSON profile
  * GET  /api/leaderboard     — top players
  * GET  /user/<user>         — public HTML page with dynamic OpenGraph tags
  * GET  /api/og-image        — on-the-fly achievement card (SVG)

The OG page + image let users post milestones to LinkedIn/X via crawler preview
cards, with zero server-side raster rendering (see README for the @vercel/og
production variant).
"""

from __future__ import annotations

from html import escape
from urllib.parse import urlencode

from flask import Blueprint, Response, g, jsonify, request

import users
from auth import login_required
from config import settings

bp = Blueprint("profile", __name__)

BADGE_LABELS = {
    "first_blood": "First Blood",
    "rookie": "Rookie",
    "on_call": "On-Call",
    "veteran": "Veteran",
    "incident_commander": "Incident Commander",
}


# --------------------------------------------------------------------------
# Award tracking
# --------------------------------------------------------------------------

@bp.post("/api/profile/solve")
@login_required
def solve():
    data = request.get_json(silent=True) or {}
    category = data.get("category", "Unix")
    difficulty = data.get("difficulty", "medium")
    profile, newly = users.record_solve(g.user["user_id"], category, difficulty)
    return jsonify({"profile": profile, "newly_earned": newly})


@bp.get("/api/profile/<username>")
def get_public_profile(username):
    prof = users.public_profile(username)
    if not prof:
        return jsonify({"error": "user not found"}), 404
    return jsonify(prof)


@bp.get("/api/leaderboard")
def leaderboard():
    return jsonify({"leaderboard": users.leaderboard()})


# --------------------------------------------------------------------------
# Dynamic OpenGraph share page
# --------------------------------------------------------------------------

def _rank_percentile(ranking: int) -> str:
    # rough, friendly framing for the share card
    if ranking >= 1800:
        return "Top 1%"
    if ranking >= 1500:
        return "Top 5%"
    if ranking >= 1300:
        return "Top 20%"
    return "Rising"


def _top_badge(badges: list[str]) -> str:
    for _thr, tag in reversed(users.MILESTONES):
        if tag in badges:
            return BADGE_LABELS.get(tag, tag)
    return "Operator"


@bp.get("/user/<username>")
def share_page(username):
    prof = users.public_profile(username)
    if not prof:
        return Response("User not found", status=404)

    rank = prof["current_ranking"]
    solved = prof["tickets_solved"]
    badge = _top_badge(prof["earned_badges"])
    pct = _rank_percentile(rank)

    og_image = f"{settings.PUBLIC_BASE_URL}/api/og-image?" + urlencode(
        {"user": username, "rank": rank, "solved": solved, "badge": badge}
    )
    page_url = f"{settings.PUBLIC_BASE_URL}/user/{username}"
    title = f"SRE Incident Commander Portfolio: {username}"
    desc = (f"🔥 Rank: {rank} Elo ({pct}) | 🛠️ Incidents Solved: {solved} | "
            f"🎖️ Specialty: {badge}. View my live verification profile on StackTrace.run.")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{escape(title)}</title>
  <meta property="og:title" content="{escape(title)}" />
  <meta property="og:description" content="{escape(desc)}" />
  <meta property="og:type" content="website" />
  <meta property="og:url" content="{escape(page_url)}" />
  <meta property="og:image" content="{escape(og_image)}" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="{escape(title)}" />
  <meta name="twitter:description" content="{escape(desc)}" />
  <meta name="twitter:image" content="{escape(og_image)}" />
  <style>
    body {{ background:#0a0e14; color:#c5d1de; font-family:ui-monospace,monospace;
            display:flex; min-height:100vh; align-items:center; justify-content:center; margin:0; }}
    .card {{ border:1px solid #1f2a37; border-radius:12px; padding:32px 40px; background:#0f141b; max-width:560px; }}
    h1 {{ color:#36d399; margin:0 0 4px; }}
    .stats {{ display:flex; gap:28px; margin-top:18px; }}
    .stat b {{ font-size:28px; color:#fff; display:block; }}
    .stat span {{ font-size:11px; color:#6b7c8f; letter-spacing:1px; }}
    img {{ width:100%; border-radius:8px; margin-top:20px; border:1px solid #1f2a37; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>@{escape(username)}</h1>
    <div style="color:#6b7c8f">StackTrace.run verification profile</div>
    <div class="stats">
      <div class="stat"><b>{rank}</b><span>ELO · {escape(pct)}</span></div>
      <div class="stat"><b>{solved}</b><span>INCIDENTS SOLVED</span></div>
      <div class="stat"><b>{escape(badge)}</b><span>TOP BADGE</span></div>
    </div>
    <img src="{escape(og_image)}" alt="achievement card" />
  </div>
</body>
</html>"""
    return Response(html, mimetype="text/html")


# --------------------------------------------------------------------------
# Zero-cost dynamic OG image (SVG; see README for the @vercel/og PNG variant)
# --------------------------------------------------------------------------

@bp.get("/api/og-image")
def og_image():
    user = escape(request.args.get("user", "anonymous"))
    rank = escape(request.args.get("rank", "1200"))
    solved = escape(request.args.get("solved", "0"))
    badge = escape(request.args.get("badge", "Operator"))

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <rect width="1200" height="630" fill="#0a0e14"/>
  <rect x="40" y="40" width="1120" height="550" rx="20" fill="#0f141b" stroke="#1f2a37" stroke-width="2"/>
  <text x="90" y="140" fill="#36d399" font-family="monospace" font-size="34" font-weight="bold">StackTrace.run // verification profile</text>
  <text x="90" y="245" fill="#ffffff" font-family="monospace" font-size="76" font-weight="bold">@{user}</text>
  <line x1="90" y1="300" x2="1110" y2="300" stroke="#1f2a37" stroke-width="2"/>
  <g font-family="monospace">
    <text x="90"  y="420" fill="#36d399" font-size="96" font-weight="bold">{rank}</text>
    <text x="90"  y="470" fill="#6b7c8f" font-size="28">ELO RANKING</text>
    <text x="520" y="420" fill="#4fd6e0" font-size="96" font-weight="bold">{solved}</text>
    <text x="520" y="470" fill="#6b7c8f" font-size="28">INCIDENTS SOLVED</text>
    <text x="870" y="420" fill="#f5c451" font-size="46" font-weight="bold">{badge}</text>
    <text x="870" y="470" fill="#6b7c8f" font-size="28">TOP BADGE</text>
  </g>
  <text x="90" y="560" fill="#6b7c8f" font-family="monospace" font-size="26">🔥 Live incident-response credentials · stacktrace.run</text>
</svg>"""
    return Response(svg, mimetype="image/svg+xml",
                    headers={"Cache-Control": "public, max-age=300"})
