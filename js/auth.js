/* ============================================================
   auth.js — frontend bridge to the StackTrace.run backend (MEMO 1.2).
   Owns: native login/signup, GitHub OAuth return, JWT storage,
   the auth-view form, the in-game user chip, and solve syncing.
   Emits onChange() so the view controller (app.js) can route
   between the auth / dashboard / game screens.
   ============================================================ */

(function () {
  'use strict';

  const API_BASE = window.STACKTRACE_API_BASE || "";

  const TOKEN_KEY = 'stacktrace_token';

  const state = { token: null, user: null, profile: null };
  const subscribers = [];

  /* --- low-level API helper --- */
  async function api(path, { method = 'GET', body, auth = false } = {}) {
    const headers = { 'Content-Type': 'application/json' };
    if (auth && state.token) headers['Authorization'] = `Bearer ${state.token}`;
    const res = await fetch(API_BASE + path, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || `request failed (${res.status})`);
    return data;
  }

  /* --- subscriptions (login/logout identity changes) --- */
  function onChange(fn) { subscribers.push(fn); }
  function notify() { subscribers.forEach((fn) => { try { fn(); } catch (_) {} }); }

  /* --- session lifecycle --- */
  function setSession(token, user, profile) {
    state.token = token;
    state.user = user;
    state.profile = profile;
    if (token) localStorage.setItem(TOKEN_KEY, token);
    renderChip();
    notify();
  }

  function logout() {
    state.token = state.user = state.profile = null;
    localStorage.removeItem(TOKEN_KEY);
    renderChip();
    notify();
  }

  async function signup(username, password, email) {
    const d = await api('/api/auth/signup', { method: 'POST', body: { username, password, email } });
    setSession(d.token, d.user, d.profile);
    return d;
  }

  async function login(username, password) {
    const d = await api('/api/auth/login', { method: 'POST', body: { username, password } });
    setSession(d.token, d.user, d.profile);
    return d;
  }

  async function fetchMe() {
    const d = await api('/api/auth/me', { auth: true });
    setSession(state.token, d.user, d.profile);
    return d;
  }

  /** Record a solved ticket. Returns null if logged out. Does NOT re-route views. */
  async function recordSolve(category, difficulty) {
    if (!state.token) return null;
    try {
      const d = await api('/api/profile/solve', {
        method: 'POST', auth: true, body: { category, difficulty },
      });
      state.profile = d.profile;
      renderChip();
      return d; // { profile, newly_earned }
    } catch (e) {
      console.warn('solve sync failed:', e.message);
      return null;
    }
  }

  async function fetchLeaderboard() {
    try { return (await api('/api/leaderboard')).leaderboard || []; }
    catch { return []; }
  }

  // --- admin ---
  const isAdmin = () => !!(state.user && state.user.is_admin);

  async function adminListUsers() {
    return (await api('/api/admin/users', { auth: true })).users || [];
  }

  async function adminDeleteUser(username) {
    return api('/api/admin/users/' + encodeURIComponent(username),
               { method: 'DELETE', auth: true });
  }

  const isAuthed = () => !!state.token;
  const currentUser = () => state.user;
  const getProfile = () => state.profile;

  /* ========================================================
     UI — in-game user chip (#auth-slot)
     ======================================================== */
  function renderChip() {
    const slot = document.getElementById('auth-slot');
    if (!slot) return;
    if (!state.user) { slot.innerHTML = ''; return; }

    const p = state.profile || {};
    const badges = badgeString(p.earned_badges);
    const shareUrl = `${API_BASE}/user/${encodeURIComponent(state.user.username)}`;
    slot.innerHTML = `
      <div class="user-chip">
        <span class="chip-name">@${escapeHtml(state.user.username)}</span>
        <span class="chip-stat">${p.current_ranking ?? 1200} <i>Elo</i></span>
        <span class="chip-stat">🛠️ ${p.tickets_solved ?? 0}</span>
        ${badges ? `<span class="chip-badges" title="badges">${badges}</span>` : ''}
        <a class="chip-link" href="${shareUrl}" target="_blank" rel="noopener" title="Public profile">share</a>
      </div>`;
  }

  function parseBadges(badges) {
    if (Array.isArray(badges)) return badges;
    if (typeof badges === 'string') { try { return JSON.parse(badges || '[]'); } catch { return []; } }
    return [];
  }

  const BADGE_ICON = {
    first_blood: '🩸', rookie: '🎯', on_call: '📟', veteran: '🎖️', incident_commander: '⭐',
  };
  function badgeString(badges) {
    const list = parseBadges(badges);
    return list.length ? list.map((b) => BADGE_ICON[b] || '🏅').join('') : '';
  }

  /* ========================================================
     UI — auth-view form (login / signup tabs)
     ======================================================== */
  let mode = 'login';

  function syncForm() {
    document.querySelectorAll('#auth-tabs button').forEach((b) =>
      b.classList.toggle('active', b.dataset.tab === mode));
    document.getElementById('auth-email').classList.toggle('hidden', mode !== 'signup');
    document.getElementById('auth-submit').textContent =
      mode === 'signup' ? 'Create account' : 'Log in';
    setError('');
  }

  function setError(msg) {
    const e = document.getElementById('auth-error');
    if (e) { e.textContent = msg || ''; e.classList.toggle('hidden', !msg); }
  }

  async function submitForm() {
    const username = document.getElementById('auth-username').value.trim();
    const password = document.getElementById('auth-password').value;
    const email = document.getElementById('auth-email').value.trim();
    const btn = document.getElementById('auth-submit');
    btn.disabled = true;
    try {
      if (mode === 'signup') await signup(username, password, email || undefined);
      else await login(username, password);
      // success -> notify() routes to the dashboard via app.js
    } catch (e) {
      setError(e.message);
    } finally {
      btn.disabled = false;
    }
  }

  function resetForm() {
    mode = 'login';
    ['auth-username', 'auth-password', 'auth-email'].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.value = '';
    });
    syncForm();
  }

  function bindForm() {
    document.querySelectorAll('#auth-tabs button').forEach((b) => {
      b.onclick = () => { mode = b.dataset.tab; syncForm(); };
    });
    document.getElementById('auth-submit').onclick = submitForm;
    document.getElementById('auth-github').onclick = () => {
      window.location.href = `${API_BASE}/api/auth/github/login`;
    };
    ['auth-username', 'auth-password', 'auth-email'].forEach((id) => {
      document.getElementById(id).addEventListener('keydown', (e) => {
        if (e.key === 'Enter') submitForm();
      });
    });
  }

  /* ========================================================
     Boot
     ======================================================== */
  async function init() {
    bindForm();

    // Capture a JWT handed back by GitHub OAuth (?token=...).
    const params = new URLSearchParams(location.search);
    const handed = params.get('token');
    if (handed) {
      state.token = handed;
      localStorage.setItem(TOKEN_KEY, handed);
      params.delete('token');
      const qs = params.toString();
      history.replaceState({}, '', location.pathname + (qs ? '?' + qs : ''));
    } else {
      state.token = localStorage.getItem(TOKEN_KEY);
    }

    // Validate any stored token; drop it if expired/invalid.
    if (state.token) {
      try { await fetchMe(); }   // fires notify() on success
      catch { logout(); }        // fires notify() -> auth view
    } else {
      notify();                  // no session -> auth view
    }
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  window.Auth = {
    init, onChange, login, signup, logout, fetchMe, recordSolve, fetchLeaderboard,
    isAuthed, currentUser, getProfile, parseBadges, badgeString, resetForm, API_BASE,
    isAdmin, adminListUsers, adminDeleteUser,
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
