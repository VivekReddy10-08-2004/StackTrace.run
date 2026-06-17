/* ============================================================
   app.js — view controller / router for the three screens:
     auth-view  →  dashboard-view  →  game-view
   Gates the game behind login, renders the dashboard from the
   user's profile, and starts a shift when "Start Playing" is hit.
   ============================================================ */

(function () {
  'use strict';

  const views = {
    auth: document.getElementById('auth-view'),
    dashboard: document.getElementById('dashboard-view'),
    game: document.getElementById('game-view'),
  };
  let currentView = 'auth';

  function show(name) {
    currentView = name;
    Object.entries(views).forEach(([k, el]) => el.classList.toggle('hidden', k !== name));
  }

  const AppView = {
    showAuth() { show('auth'); if (window.Auth && Auth.resetForm) Auth.resetForm(); },
    showDashboard() { show('dashboard'); renderDashboard(); },
    showGame() { show('game'); },
  };
  window.AppView = AppView;

  /* --- routing: react to login / logout --- */
  function route() {
    if (!Auth.isAuthed()) { AppView.showAuth(); return; }
    if (currentView === 'game') return;   // never yank a player out of a shift
    AppView.showDashboard();
  }

  /* --- dashboard rendering --- */
  function renderDashboard() {
    const user = Auth.currentUser();
    if (!user) return;
    const p = Auth.getProfile() || {};

    document.getElementById('dash-username').textContent = '@' + user.username;
    document.getElementById('dash-elo').textContent = p.current_ranking ?? 1200;
    document.getElementById('dash-solved').textContent = p.tickets_solved ?? 0;
    document.getElementById('dash-streak').textContent = p.current_streak ?? 0;
    document.getElementById('dash-badges').textContent =
      Auth.badgeString(p.earned_badges) || '—';

    const share = document.getElementById('dash-share');
    share.href = `${Auth.API_BASE}/user/${encodeURIComponent(user.username)}`;

    renderLevels();
    renderLeaderboard(user.username);
  }

  function renderLevels() {
    const ul = document.getElementById('dash-levels');
    const items = (window.Game && Game.summary()) || [];
    ul.innerHTML = items.map((l) => `
      <li>
        <span class="lvl-tag lvl-${l.type}">${l.type.toUpperCase()}</span>
        <span class="lvl-title">${escapeHtml(l.title)}</span>
      </li>`).join('') || '<li class="muted">No incidents loaded.</li>';
  }

  async function renderLeaderboard(me) {
    const ol = document.getElementById('dash-leaderboard');
    ol.innerHTML = '<li class="muted">loading…</li>';
    const rows = await Auth.fetchLeaderboard();
    if (!rows.length) { ol.innerHTML = '<li class="muted">no players yet</li>'; return; }
    ol.innerHTML = rows.map((r, i) => `
      <li class="${r.username === me ? 'me' : ''}">
        <span class="lb-rank">#${i + 1}</span>
        <span class="lb-name">@${escapeHtml(r.username)}</span>
        <span class="lb-elo">${r.current_ranking} Elo</span>
      </li>`).join('');
  }

  /* --- actions --- */
  function selectedMode() {
    const r = document.querySelector('input[name="mode"]:checked');
    return r ? r.value : 'curated';
  }

  function bindActions() {
    document.getElementById('play-btn').onclick = () => {
      AppView.showGame();
      Game.start(selectedMode());
    };
    document.getElementById('dash-logout').onclick = () => Auth.logout();
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  /* --- boot --- */
  function init() {
    bindActions();
    Auth.onChange(route);
    route();   // set the initial screen from current auth state
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
