/* ============================================================
   game.js — the state machine that ties everything together.
   Owns: the active level, the virtual file system, the sql.js
   database, the countdown clock, scoring, the command parser,
   the nano editor modal, and win/lose modals.
   ============================================================ */

(function () {
  'use strict';

  const HOSTNAME = 'prod-01';
  const USER = 'root';
  const LEVEL_SECONDS = 300; // 5-minute "System Uptime" per ticket

  /* --- base file system shared by every level --- */
  function baseTree() {
    const D = FileSystem.dir, F = FileSystem.file;
    return D({
      bin:  D({}),
      etc:  D({ 'hostname': F(HOSTNAME + '\n') }),
      home: D({ devops: D({ 'README.txt': F('Welcome to DEV-SIM. Fix the tickets. Good luck.\n') }) }),
      opt:  D({ scripts: D({}) }),
      root: D({ '.bashrc': F('# root shell\n') }),
      var:  D({ log: D({ 'syslog': F('system nominal\n') }) })
    });
  }

  /* --- DOM handles --- */
  const el = {
    output:      document.getElementById('terminal-output'),
    input:       document.getElementById('terminal-input'),
    prompt:      document.getElementById('prompt'),
    termTitle:   document.getElementById('terminal-title'),
    feed:        document.getElementById('ticket-feed'),
    levelInd:    document.getElementById('level-indicator'),
    scoreInd:    document.getElementById('score-indicator'),
    timer:       document.getElementById('timer'),
    uptime:      document.querySelector('.uptime'),
    editorOverlay: document.getElementById('editor-overlay'),
    editorTextarea: document.getElementById('editor-textarea'),
    editorFilename: document.getElementById('editor-filename'),
    editorSave:  document.getElementById('editor-save'),
    editorExit:  document.getElementById('editor-exit'),
    resultOverlay: document.getElementById('result-overlay'),
    resultWindow:  document.getElementById('result-window'),
    resultIcon:    document.getElementById('result-icon'),
    resultTitle:   document.getElementById('result-title'),
    resultMessage: document.getElementById('result-message'),
    resultButton:  document.getElementById('result-button')
  };

  /* --- runtime state --- */
  const state = {
    levelIndex: 0,
    score: 0,
    fs: null,
    db: null,            // active sql.js database (level 3)
    SQL: null,           // sql.js module
    timeLeft: LEVEL_SECONDS,
    timerHandle: null,
    editingPath: null,
    solved: false,
    gameOver: false
  };

  let term;
  let CURATED = [];   // pristine snapshot of the built-in levels

  /* ===========================================================
     Boot — sets up the engine but does NOT start a shift.
     The dashboard calls Game.start(mode) when the player hits Play.
     =========================================================== */
  function boot() {
    term = new Terminal({
      output: el.output,
      input: el.input,
      promptEl: el.prompt,
      onCommand: handleCommand
    });

    bindModals();
    CURATED = LEVELS.slice();   // remember the built-in set

    // Load sql.js up-front so the SQL level is instant. Falls back gracefully.
    if (window.initSqlJs) {
      initSqlJs({
        locateFile: (f) => `https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.10.3/${f}`
      }).then((SQL) => { state.SQL = SQL; }).catch(() => { state.SQL = null; });
    }

    const back = document.getElementById('back-to-dash');
    if (back) back.onclick = exitToDashboard;
  }

  /** Swap the active level set in place so global refs stay valid. */
  function setLevels(arr) {
    LEVELS.length = 0;
    arr.forEach((l) => LEVELS.push(l));
  }

  function resetState() {
    clearInterval(state.timerHandle);
    state.levelIndex = 0;
    state.score = 0;
    state.solved = false;
    state.gameOver = false;
    state.lastSql = null;
    el.scoreInd.textContent = '0';
    el.resultOverlay.classList.add('hidden');
    term.clear();
  }

  /** Entry point used by the dashboard. mode: 'curated' | 'generated'. */
  async function startGame(mode) {
    resetState();
    if (mode === 'generated' && window.GeneratedLevels) {
      try {
        const gen = await GeneratedLevels.load();
        setLevels(gen.length ? gen : CURATED);
        if (!gen.length) term.print('No generated levels found — using curated set.', 'line-amber');
      } catch (e) {
        setLevels(CURATED);
        term.print('Could not load generated levels — using curated set.', 'line-amber');
      }
    } else {
      setLevels(CURATED);
    }
    welcome();
    loadLevel(0);
    term.focus();
  }

  function exitToDashboard() {
    clearInterval(state.timerHandle);
    if (window.AppView) AppView.showDashboard();
  }

  function welcome() {
    term.print('StackTrace.run console — you are on call.', 'line-ok');
    term.print('Tickets appear on the left. Resolve them before uptime hits 00:00.', 'line-dim');
    term.print("Type 'help' for available commands. Type 'hint' if you get stuck.", 'line-dim');
    term.print('');
  }

  /* ===========================================================
     Level lifecycle
     =========================================================== */
  function loadLevel(index) {
    if (index >= LEVELS.length) return winGame();

    const lvl = LEVELS[index];
    state.levelIndex = index;
    state.solved = false;

    // Fresh world for this ticket.
    state.fs = new FileSystem(baseTree(), lvl.home || '/root');
    if (typeof lvl.build === 'function') lvl.build(state.fs);

    // Fresh database if the level needs SQL.
    state.db = null;
    if (lvl.type === 'sql' && state.SQL) {
      state.db = new state.SQL.Database();
      state.db.run(lvl.sql);
    }

    el.levelInd.textContent = `${index + 1} / ${LEVELS.length}`;
    renderTickets();
    updatePrompt();
    resetTimer();

    term.print(`── New ticket assigned: ${lvl.id} ─────────────`, 'line-info');
    term.print(`"${lvl.title}"`, 'line-amber');
    term.print('');
  }

  function renderTickets() {
    el.feed.innerHTML = '';
    LEVELS.forEach((lvl, i) => {
      if (i > state.levelIndex) return; // only reveal up to current
      const solved = i < state.levelIndex || (i === state.levelIndex && state.solved);
      const card = document.createElement('div');
      card.className = 'ticket' + (solved ? ' solved' : '');
      const prio = lvl.priority === 'high' ? 'priority-high' : 'priority-med';
      card.innerHTML = `
        <div class="ticket-head">
          <span class="ticket-id">${lvl.id}</span>
          <span class="ticket-priority ${prio}">${lvl.priority.toUpperCase()}</span>
        </div>
        <div class="ticket-title">${lvl.title}</div>
        <div class="ticket-body">${lvl.body}</div>
        <div class="ticket-goal">${lvl.goal}</div>
        ${solved ? '<div class="ticket-status">✔ RESOLVED</div>' : ''}
      `;
      el.feed.appendChild(card);
    });
  }

  /* ===========================================================
     Timer
     =========================================================== */
  function resetTimer() {
    clearInterval(state.timerHandle);
    state.timeLeft = LEVEL_SECONDS;
    renderTimer();
    state.timerHandle = setInterval(tick, 1000);
  }

  function tick() {
    state.timeLeft--;
    renderTimer();
    if (state.timeLeft <= 0) {
      clearInterval(state.timerHandle);
      failGame("System uptime hit 00:00 — the service crashed before you resolved the ticket.");
    }
  }

  function renderTimer() {
    const m = String(Math.floor(state.timeLeft / 60)).padStart(2, '0');
    const s = String(state.timeLeft % 60).padStart(2, '0');
    el.timer.textContent = `${m}:${s}`;
    el.uptime.classList.toggle('warning', state.timeLeft <= 60 && state.timeLeft > 20);
    el.uptime.classList.toggle('critical', state.timeLeft <= 20);
  }

  /* ===========================================================
     Prompt
     =========================================================== */
  function updatePrompt() {
    const cwd = state.fs.pwd();
    const home = state.fs.home;
    let shown = cwd;
    if (cwd === home) shown = '~';
    else if (cwd.startsWith(home + '/')) shown = '~' + cwd.slice(home.length);
    el.prompt.textContent = `${USER}@${HOSTNAME}:${shown}$`;
    el.termTitle.textContent = `${USER}@${HOSTNAME}: ${shown}`;
  }

  /* ===========================================================
     Command parser  — the heart of the simulator
     =========================================================== */
  function handleCommand(raw) {
    if (state.gameOver) return;
    const input = raw.trim();
    if (!input) return;

    // Pro-tip from the MEMO: normalise the verb, keep args intact.
    const parts = input.split(/\s+/);
    const cmd = parts[0].toLowerCase();
    const args = parts.slice(1);

    const fs = state.fs;

    switch (cmd) {
      case 'help':    cmdHelp(); break;
      case 'clear':   term.clear(); break;
      case 'hint':    term.print('💡 ' + LEVELS[state.levelIndex].hint, 'line-amber'); break;
      case 'whoami':  term.print(USER); break;
      case 'hostname':term.print(HOSTNAME); break;
      case 'pwd':     term.print(fs.pwd()); break;
      case 'echo':    term.print(args.join(' ')); break;

      case 'ls': {
        const r = fs.list(args[0] || '.');
        if (r.error) term.print(r.error, 'line-err');
        else term.print(r.entries.join('   '));
        break;
      }

      case 'cd': {
        const r = fs.cd(args[0] || fs.home);
        if (r.error) term.print(r.error, 'line-err');
        else updatePrompt();
        break;
      }

      case 'cat': {
        if (!args[0]) { term.print('cat: missing file operand', 'line-err'); break; }
        const r = fs.read(args[0]);
        if (r.error) term.print(r.error, 'line-err');
        else term.printLines(r.content);
        break;
      }

      case 'rm': {
        const target = args.filter(a => !a.startsWith('-')).pop();
        const recursive = args.includes('-r') || args.includes('-rf') || args.includes('-fr');
        if (!target) { term.print('rm: missing operand', 'line-err'); break; }
        const r = recursive ? fs.removeDir(target) : fs.remove(target);
        if (r.error) term.print(r.error, 'line-err');
        break;
      }

      case 'nano':
      case 'vim':
      case 'vi': {
        if (!args[0]) { term.print(`${cmd}: missing file operand`, 'line-err'); break; }
        openEditor(args[0]);
        break;
      }

      case 'sql': {
        runSql(input.slice(input.indexOf('sql') + 3).trim());
        break;
      }

      default:
        term.print(`${cmd}: command not found`, 'line-err');
    }

    // After every action, re-evaluate the win condition.
    checkSolved();
  }

  function cmdHelp() {
    const rows = [
      ['help',            'show this help'],
      ['clear',           'clear the screen  (Ctrl+L)'],
      ['hint',            'reveal a hint for the current ticket'],
      ['ls [path]',       'list directory contents'],
      ['cd <path>',       'change directory  (supports .. ~ /)'],
      ['pwd',             'print working directory'],
      ['cat <file>',      'print a file'],
      ['rm [-r] <path>',  'remove a file (or directory with -r)'],
      ['nano <file>',     'edit a file in the popup editor'],
      ['sql <query>',     'run a SQL query against the live database'],
      ['whoami / echo',   'the usual'],
    ];
    term.print('Available commands:', 'line-info');
    rows.forEach(([c, d]) => term.print('  ' + c.padEnd(18) + d, 'line-dim'));
  }

  /* ===========================================================
     SQL execution (sql.js)
     =========================================================== */
  function runSql(query) {
    state.lastSql = query;
    if (!query) { term.print('sql: provide a query, e.g. sql SELECT * FROM users;', 'line-err'); return; }
    if (LEVELS[state.levelIndex].type !== 'sql' || !state.db) {
      if (!state.SQL) term.print('sql: database engine still loading, try again in a moment…', 'line-err');
      else term.print('sql: no database is attached to this ticket.', 'line-err');
      return;
    }
    try {
      const res = state.db.exec(query);
      if (!res.length) {
        term.print('OK', 'line-ok');
        return;
      }
      res.forEach((r) => term.printLines(formatTable(r.columns, r.values), 'line-out'));
    } catch (e) {
      term.print('SQL error: ' + e.message, 'line-err');
    }
  }

  /** Render a result set as an aligned ASCII table. */
  function formatTable(columns, values) {
    const widths = columns.map((c, i) =>
      Math.max(String(c).length, ...values.map(row => String(row[i]).length)));
    const sep = '+' + widths.map(w => '-'.repeat(w + 2)).join('+') + '+';
    const fmtRow = (cells) =>
      '| ' + cells.map((c, i) => String(c).padEnd(widths[i])).join(' | ') + ' |';
    return [sep, fmtRow(columns), sep, ...values.map(fmtRow), sep].join('\n');
  }

  /* ===========================================================
     Nano editor modal
     =========================================================== */
  function openEditor(path) {
    const fs = state.fs;
    const resolved = fs.resolve(path);
    const node = fs.node(resolved);
    if (node && node.type === 'dir') {
      term.print(`nano: ${path}: Is a directory`, 'line-err');
      return;
    }
    state.editingPath = resolved;
    el.editorFilename.textContent = resolved;
    el.editorTextarea.value = node ? node.content : '';
    el.editorOverlay.classList.remove('hidden');
    el.editorTextarea.focus();
  }

  function saveEditor() {
    if (state.editingPath) {
      state.fs.write(state.editingPath, el.editorTextarea.value);
      term.print(`[ Wrote ${state.editingPath} ]`, 'line-dim');
    }
    closeEditor();
    checkSolved();
  }

  function closeEditor() {
    el.editorOverlay.classList.add('hidden');
    state.editingPath = null;
    term.focus();
  }

  /* ===========================================================
     Win-condition evaluation
     =========================================================== */
  function checkSolved() {
    if (state.solved || state.gameOver) return;
    const lvl = LEVELS[state.levelIndex];
    const ctx = {
      fs: state.fs,
      db: state.db,
      history: term ? term.history : [],
      lastSql: state.lastSql,
    };
    let ok = false;
    try { ok = lvl.check(ctx); } catch (e) { ok = false; }
    if (ok) solveLevel(lvl);
  }

  function solveLevel(lvl) {
    state.solved = true;
    clearInterval(state.timerHandle);
    const bonus = Math.max(50, state.timeLeft);   // reward speed
    state.score += 100 + bonus;
    el.scoreInd.textContent = state.score;
    renderTickets();

    term.print('');
    term.print('✔ Ticket resolved! +' + (100 + bonus) + ' pts', 'line-ok');

    syncSolve(lvl);

    showResult(true, lvl.successMsg,
      state.levelIndex + 1 < LEVELS.length ? 'Next Ticket →' : 'See Results →');
  }

  /** Persist the solve to the backend (rank/streak/badges) if logged in. */
  function syncSolve(lvl) {
    if (!window.Auth || !Auth.isAuthed()) return;
    const category = { unix: 'Unix', python: 'Python', sql: 'SQL' }[lvl.type] || 'Unix';
    const difficulty = lvl.difficulty || (lvl.priority === 'high' ? 'hard' : 'medium');
    Auth.recordSolve(category, difficulty).then((res) => {
      if (!res) return;
      term.print(`☁ Synced to @${Auth.currentUser().username} — ` +
        `${res.profile.current_ranking} Elo, streak ${res.profile.current_streak}`, 'line-info');
      (res.newly_earned || []).forEach((b) =>
        term.print(`🏆 Badge unlocked: ${b.replace(/_/g, ' ')}`, 'line-amber'));
    });
  }

  /* ===========================================================
     Result / game-over modals
     =========================================================== */
  function showResult(success, message, buttonLabel) {
    el.resultWindow.classList.toggle('success', success);
    el.resultWindow.classList.toggle('failure', !success);
    el.resultIcon.textContent = success ? '✔' : '✖';
    el.resultTitle.textContent = success ? 'Ticket Resolved!' : 'Incident Failed';
    el.resultMessage.textContent = message;
    el.resultButton.textContent = buttonLabel;
    el.resultOverlay.classList.remove('hidden');
  }

  function winGame() {
    state.gameOver = true;
    clearInterval(state.timerHandle);
    showResult(true,
      `All tickets resolved. Final score: ${state.score}. ` +
      `You survived your shift as junior on-call. 🎉`, 'Back to Dashboard →');
    el.resultTitle.textContent = 'Shift Complete!';
  }

  function failGame(message) {
    state.gameOver = true;
    clearInterval(state.timerHandle);
    showResult(false, message + ` Final score: ${state.score}.`, 'Back to Dashboard →');
  }

  function advanceFromResult() {
    el.resultOverlay.classList.add('hidden');
    if (state.gameOver) {
      // Shift is over — return to the dashboard with refreshed stats.
      exitToDashboard();
      return;
    }
    loadLevel(state.levelIndex + 1);
    term.focus();
  }

  /* ===========================================================
     Modal wiring
     =========================================================== */
  function bindModals() {
    el.editorSave.addEventListener('click', saveEditor);
    el.editorExit.addEventListener('click', closeEditor);

    el.editorTextarea.addEventListener('keydown', (e) => {
      // Ctrl+O save, Ctrl+X exit — like real nano.
      if (e.ctrlKey && e.key.toLowerCase() === 'o') { e.preventDefault(); saveEditor(); }
      if (e.ctrlKey && e.key.toLowerCase() === 'x') { e.preventDefault(); closeEditor(); }
      // Allow real tabs inside the editor.
      if (e.key === 'Tab') {
        e.preventDefault();
        const s = e.target.selectionStart, en = e.target.selectionEnd;
        e.target.value = e.target.value.slice(0, s) + '    ' + e.target.value.slice(en);
        e.target.selectionStart = e.target.selectionEnd = s + 4;
      }
    });

    el.resultButton.addEventListener('click', advanceFromResult);
  }

  /* --- public API for the view controller --- */
  window.Game = {
    start: startGame,
    summary: () => CURATED.map((l) => ({ id: l.id, title: l.title, type: l.type })),
  };

  /* --- go (engine setup only; no shift starts yet) --- */
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
