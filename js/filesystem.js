/* ============================================================
   filesystem.js — virtual Unix file system
   A nested JS object models directories and files. No real OS
   is ever touched. Supports absolute + relative path resolution
   including `.`, `..`, `~`, and `/`.
   ============================================================ */

class FileSystem {
  /**
   * @param {object} tree  root directory node
   * @param {string} home  starting working directory
   */
  constructor(tree, home = '/') {
    this.root = tree;
    this.home = home;
    this.cwd = home;
  }

  // --- factory helpers used by level data ---
  static dir(children = {}) { return { type: 'dir', children }; }
  static file(content = '')  { return { type: 'file', content }; }

  /** Split a path into clean segments, resolving ~ to home. */
  _segments(path) {
    if (path === '~' || path.startsWith('~/')) {
      path = this.home + path.slice(1);
    }
    const base = path.startsWith('/') ? [] : this.cwd.split('/').filter(Boolean);
    for (const part of path.split('/')) {
      if (part === '' || part === '.') continue;
      if (part === '..') base.pop();
      else base.push(part);
    }
    return base;
  }

  /** Normalise a path to an absolute string. */
  resolve(path) {
    return '/' + this._segments(path).join('/');
  }

  /** Walk the tree and return the node at `path`, or null. */
  node(path) {
    const segs = this._segments(path);
    let cur = this.root;
    for (const seg of segs) {
      if (!cur || cur.type !== 'dir' || !cur.children[seg]) return null;
      cur = cur.children[seg];
    }
    return cur;
  }

  /** Parent node + final name, for create/delete operations. */
  _parentAndName(path) {
    const segs = this._segments(path);
    const name = segs.pop();
    const parent = this.node('/' + segs.join('/'));
    return { parent, name };
  }

  exists(path)  { return this.node(path) !== null; }
  isDir(path)   { const n = this.node(path); return !!n && n.type === 'dir'; }
  isFile(path)  { const n = this.node(path); return !!n && n.type === 'file'; }

  list(path = '.') {
    const n = this.node(path);
    if (!n) return { error: `ls: cannot access '${path}': No such file or directory` };
    if (n.type === 'file') return { entries: [path.split('/').pop()] };
    return { entries: Object.keys(n.children).sort() };
  }

  cd(path) {
    const n = this.node(path);
    if (!n) return { error: `cd: ${path}: No such file or directory` };
    if (n.type !== 'dir') return { error: `cd: ${path}: Not a directory` };
    this.cwd = this.resolve(path);
    return { ok: true };
  }

  read(path) {
    const n = this.node(path);
    if (!n) return { error: `cat: ${path}: No such file or directory` };
    if (n.type === 'dir') return { error: `cat: ${path}: Is a directory` };
    return { content: n.content };
  }

  /** Overwrite (or create) a file's contents — used by the nano editor. */
  write(path, content) {
    const { parent, name } = this._parentAndName(path);
    if (!parent || parent.type !== 'dir') {
      return { error: `cannot write ${path}: No such directory` };
    }
    parent.children[name] = FileSystem.file(content);
    return { ok: true };
  }

  remove(path) {
    const { parent, name } = this._parentAndName(path);
    if (!parent || !parent.children[name]) {
      return { error: `rm: cannot remove '${path}': No such file or directory` };
    }
    if (parent.children[name].type === 'dir') {
      return { error: `rm: cannot remove '${path}': Is a directory (use rm -r)` };
    }
    delete parent.children[name];
    return { ok: true };
  }

  removeDir(path) {
    const { parent, name } = this._parentAndName(path);
    if (!parent || !parent.children[name]) {
      return { error: `rm: cannot remove '${path}': No such file or directory` };
    }
    delete parent.children[name];
    return { ok: true };
  }

  pwd() { return this.cwd; }
}

window.FileSystem = FileSystem;
