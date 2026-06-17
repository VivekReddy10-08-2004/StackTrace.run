/* ============================================================
   generated-levels.js — bridge between the Python pipeline and
   the web terminal. Loads src/levels/manifest.json + each
   level_N.json (the schema from project_Architecture.md) and
   adapts them into the runtime level format the game expects.

   Enabled by opening the app with ?source=generated
   ============================================================ */

(function () {
  'use strict';

  const STOPWORDS = new Set(
    ('the a an to of in for on and or with using such as that this is are be ' +
     'must should which value file files code command string pattern issue ' +
     'error correct fix run running typically achieved involves your you it')
      .split(' ')
  );

  /* --- extract the checkable pattern(s) from a prose hint --- */
  function extractPatterns(hint) {
    if (!hint) return [];
    const quoted = [];
    const re = /`([^`]+)`|'([^']+)'|"([^"]+)"/g;
    let m;
    while ((m = re.exec(hint)) !== null) {
      const snip = (m[1] || m[2] || m[3] || '').trim();
      if (snip.length >= 3) quoted.push(snip);
    }
    if (quoted.length) return quoted.map(normalize);

    // Fallback: the single most distinctive code-ish token in the hint.
    const tokens = (hint.match(/[A-Za-z0-9_.+\-/]{4,}/g) || [])
      .filter((t) => !STOPWORDS.has(t.toLowerCase()));
    tokens.sort((a, b) => b.length - a.length);
    return tokens.length ? [normalize(tokens[0])] : [];
  }

  function normalize(s) {
    return String(s).toLowerCase().replace(/\s+/g, ' ').trim();
  }

  /* --- gather everything the player has produced into one haystack --- */
  function buildHaystack(ctx) {
    const parts = [];
    walkFiles(ctx.fs.root, (content) => parts.push(content));
    if (ctx.history) parts.push(ctx.history.join('\n'));
    if (ctx.lastSql) parts.push(ctx.lastSql);
    return normalize(parts.join('\n'));
  }

  function walkFiles(node, cb) {
    if (!node) return;
    if (node.type === 'file') { cb(node.content || ''); return; }
    if (node.type === 'dir') {
      for (const child of Object.values(node.children)) walkFiles(child, cb);
    }
  }

  /* --- adapt one generated JSON object into a runtime level --- */
  function adapt(data) {
    const category = (data.category || 'Unix');
    const type = category.toLowerCase(); // unix | python | sql
    const files = (data.starting_state && data.starting_state.files) || {};
    const dbSchema = data.starting_state && data.starting_state.db_schema;
    const patterns = extractPatterns(data.winning_condition_hint);

    const source = data._source && data._source.url
      ? ` <a href="${data._source.url}" target="_blank" rel="noopener" style="color:var(--cyan)">[source]</a>`
      : '';

    return {
      id: data.ticket_id || 'GEN-TICKET',
      type,
      priority: type === 'python' ? 'med' : 'high',
      title: data.title || 'Generated ticket',
      body: (data.problem_description || '') + source,
      goal: 'Resolve the issue — your fix must contain the expected pattern.',
      hint: data.winning_condition_hint || 'No hint available for this generated ticket.',
      home: '/root',

      build(fs) {
        for (const [name, content] of Object.entries(files)) {
          const path = name.includes('/') ? '/root/' + name : '/root/' + name;
          fs.write(path, content);
        }
      },

      // sql.js seed for SQL tickets (schema only; queries still run live)
      sql: type === 'sql' && dbSchema ? dbSchema : undefined,

      check(ctx) {
        if (!patterns.length) return false;
        const hay = buildHaystack(ctx);
        return patterns.some((p) => hay.includes(p));
      },

      successMsg: 'Resolved — your fix matched the expected pattern. ' +
                  'Generated from a real Stack Overflow thread.',
    };
  }

  /* --- public: load + adapt all generated levels --- */
  async function load(baseDir = 'src/levels') {
    const res = await fetch(`${baseDir}/manifest.json`, { cache: 'no-store' });
    if (!res.ok) throw new Error(`manifest.json not found (${res.status})`);
    const manifest = await res.json();
    const entries = manifest.levels || [];

    const levels = [];
    for (const entry of entries) {
      try {
        const r = await fetch(`${baseDir}/${entry.file}`, { cache: 'no-store' });
        if (!r.ok) continue;
        levels.push(adapt(await r.json()));
      } catch (e) {
        console.warn('Skipping level', entry.file, e);
      }
    }
    return levels;
  }

  window.GeneratedLevels = { load, adapt, extractPatterns };
})();
