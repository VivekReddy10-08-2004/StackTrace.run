/* ============================================================
   levels.js — game content (data first, code second).
   Each level is self-contained: the ticket text, the initial
   virtual environment, and a `check()` predicate that decides
   whether the player has solved it. Logic lives in game.js;
   this file is purely "what the world looks like".
   ============================================================ */

const D = FileSystem.dir;
const F = FileSystem.file;

const LEVELS = [
  /* ----------------------------------------------------------
     LEVEL 1 — UNIX: disk pressure from a runaway log file
     ---------------------------------------------------------- */
  {
    id: 'OPS-1042',
    type: 'unix',
    priority: 'high',
    title: 'Disk usage at 98% on prod-01',
    body: `PagerDuty is screaming. <code>/</code> is almost full and the API is about to fall over. ` +
          `A runaway log file in <code>/var/log</code> is the culprit — a debug logger was left on and ` +
          `wrote gigabytes to <code>app.debug.log</code>. Free up the space.`,
    goal: `Delete /var/log/app.debug.log`,
    hint: `Try: cd /var/log → ls → rm app.debug.log`,
    home: '/root',

    // Files merged into the base tree when the level loads.
    build(fs) {
      fs.root.children.var.children.log.children['app.debug.log'] =
        F('[DEBUG] '.repeat(2000) + '\n... 4.2 GB of noise ...');
    },

    check(ctx) {
      return !ctx.fs.exists('/var/log/app.debug.log');
    },
    successMsg: 'Disk pressure relieved. The API recovered and PagerDuty went quiet.'
  },

  /* ----------------------------------------------------------
     LEVEL 2 — PYTHON: a backup script crashes on a missing import
     ---------------------------------------------------------- */
  {
    id: 'OPS-1108',
    type: 'python',
    priority: 'med',
    title: 'Nightly backup job is crash-looping',
    body: `The cron-driven backup script <code>/opt/scripts/backup.py</code> throws ` +
          `<code>NameError: name 'time' is not defined</code> right after it starts. ` +
          `Someone added a retry delay with <code>time.sleep()</code> but forgot the import. ` +
          `Open it in nano, fix the script, and save.`,
    goal: `Add the missing import to backup.py so it no longer crashes`,
    hint: `Run: nano /opt/scripts/backup.py — then add  import time  near the top.`,
    home: '/opt/scripts',

    build(fs) {
      fs.root.children.opt.children.scripts.children['backup.py'] = F(
`#!/usr/bin/env python3
import os
import shutil

def run_backup():
    for attempt in range(3):
        try:
            shutil.copytree("/data", "/backup/data")
            print("Backup complete")
            return
        except Exception as e:
            print("Retry after error:", e)
            time.sleep(5)   # <-- uses time, but time is never imported

run_backup()
`);
    },

    check(ctx) {
      const r = ctx.fs.read('/opt/scripts/backup.py');
      if (r.error) return false;
      // The fix is satisfied when `time` is imported AND still used.
      const importsTime = /^\s*import\s+time\b/m.test(r.content) ||
                          /^\s*import\s+.*\btime\b/m.test(r.content);
      const usesTime = /time\.sleep/.test(r.content);
      return importsTime && usesTime;
    },
    successMsg: 'Script parses cleanly. The next backup run completed without errors.'
  },

  /* ----------------------------------------------------------
     LEVEL 3 — SQL: a locked-out customer account
     ---------------------------------------------------------- */
  {
    id: 'OPS-1213',
    type: 'sql',
    priority: 'high',
    title: 'VIP customer locked out of their account',
    body: `Support escalated: customer <code>ada@lovelace.io</code> can't log in. ` +
          `Their row in the <code>users</code> table got flagged <code>is_active = 0</code> ` +
          `by a buggy fraud rule. Use the <code>sql</code> command to reactivate just that account. ` +
          `Tip: <code>sql SELECT * FROM users;</code> to inspect the table first.`,
    goal: `Set is_active = 1 for ada@lovelace.io (and nobody else)`,
    hint: `sql UPDATE users SET is_active = 1 WHERE email = 'ada@lovelace.io';`,
    home: '/root',

    // SQL schema/seed for this level — loaded into sql.js.
    sql: `
      CREATE TABLE users (
        id        INTEGER PRIMARY KEY,
        email     TEXT,
        is_active INTEGER
      );
      INSERT INTO users (id, email, is_active) VALUES
        (1, 'grace@hopper.io',  1),
        (2, 'ada@lovelace.io',  0),
        (3, 'alan@turing.io',   1),
        (4, 'linus@kernel.io',  1);
    `,

    check(ctx) {
      if (!ctx.db) return false;
      const res = ctx.db.exec(
        "SELECT email, is_active FROM users WHERE is_active = 0"
      );
      // Solved when zero inactive users remain — i.e. Ada was reactivated
      // and nobody else was deactivated in the process.
      const inactive = res.length ? res[0].values.length : 0;
      // Guard against accidentally activating everyone via a blanket UPDATE:
      const total = ctx.db.exec("SELECT COUNT(*) FROM users")[0].values[0][0];
      const active = ctx.db.exec("SELECT COUNT(*) FROM users WHERE is_active = 1")[0].values[0][0];
      return inactive === 0 && active === total && total === 4;
    },
    successMsg: 'Account reactivated. Ada logged in successfully and support closed the ticket.'
  }
];

window.LEVELS = LEVELS;
