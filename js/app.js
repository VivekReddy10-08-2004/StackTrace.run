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
    renderAdmin(user.username);
  }

  async function renderAdmin(me) {
    const panel = document.getElementById('admin-panel');
    if (!panel) return;
    if (!Auth.isAdmin()) { panel.classList.add('hidden'); return; }
    panel.classList.remove('hidden');

    const box = document.getElementById('admin-users');
    box.innerHTML = '<div class="muted">loading…</div>';
    let rows;
    try { rows = await Auth.adminListUsers(); }
    catch (e) { box.innerHTML = `<div class="muted">could not load users: ${escapeHtml(e.message)}</div>`; return; }

    if (!rows.length) { box.innerHTML = '<div class="muted">no users</div>'; return; }
    box.innerHTML = rows.map((u) => `
      <div class="admin-row">
        <span class="admin-name">@${escapeHtml(u.username)}</span>
        <span class="admin-meta">${u.current_ranking ?? '—'} Elo · ${u.tickets_solved ?? 0} solved · ${escapeHtml(u.auth_provider || 'native')}</span>
        ${u.username === me
          ? '<span class="admin-you">you</span>'
          : `<button class="admin-del" data-user="${escapeHtml(u.username)}">Delete</button>`}
      </div>`).join('');

    box.querySelectorAll('.admin-del').forEach((btn) => {
      btn.onclick = async () => {
        const username = btn.dataset.user;
        if (!confirm(`Delete @${username}? This removes their account and progress.`)) return;
        btn.disabled = true;
        try { await Auth.adminDeleteUser(username); renderDashboard(); }
        catch (e) { alert('Delete failed: ' + e.message); btn.disabled = false; }
      };
    });
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
