/* ============================================================
   terminal.js — the mock terminal UI.
   Owns the output buffer, the input line, command history
   (arrow-key navigation) and tab-ish niceties. It does NOT
   know game rules — it just hands raw command strings to a
   callback supplied by game.js.
   ============================================================ */

class Terminal {
  constructor({ output, input, promptEl, onCommand }) {
    this.output = output;
    this.input = input;
    this.promptEl = promptEl;
    this.onCommand = onCommand;
    this.history = [];
    this.historyIndex = -1;

    this._bind();
  }

  _bind() {
    this.input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        this._submit();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        this._recall(-1);
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        this._recall(1);
      } else if (e.key === 'l' && e.ctrlKey) {
        e.preventDefault();
        this.clear();
      }
    });

    // Keep focus on the terminal whenever the user clicks the pane.
    this.output.parentElement.addEventListener('click', () => {
      if (!window.getSelection().toString()) this.input.focus();
    });
  }

  _submit() {
    const raw = this.input.value;
    const cmd = raw.trim();
    // Echo the command exactly as typed, with the live prompt.
    this.echoCommand(this.promptEl.textContent, raw);
    this.input.value = '';
    if (cmd) {
      this.history.push(cmd);
      this.historyIndex = this.history.length;
    }
    if (this.onCommand) this.onCommand(cmd);
  }

  _recall(dir) {
    if (!this.history.length) return;
    this.historyIndex = Math.max(0, Math.min(this.history.length, this.historyIndex + dir));
    this.input.value = this.history[this.historyIndex] || '';
    // Move cursor to end.
    requestAnimationFrame(() => {
      this.input.selectionStart = this.input.selectionEnd = this.input.value.length;
    });
  }

  /** Print a normal output line. `cls` selects a color class. */
  print(text = '', cls = 'line-out') {
    const div = document.createElement('div');
    div.className = `line ${cls}`;
    div.textContent = text;
    this.output.appendChild(div);
    this._scroll();
  }

  /** Print multiple lines at once. */
  printLines(text, cls) {
    String(text).split('\n').forEach((l) => this.print(l, cls));
  }

  /** Echo the prompt + the command the user typed. */
  echoCommand(prompt, cmd) {
    const div = document.createElement('div');
    div.className = 'line line-cmd';
    const p = document.createElement('span');
    p.className = 'echo-prompt';
    p.textContent = prompt + ' ';
    div.appendChild(p);
    div.appendChild(document.createTextNode(cmd));
    this.output.appendChild(div);
    this._scroll();
  }

  clear() { this.output.innerHTML = ''; }

  setPrompt(text) { this.promptEl.textContent = text; }

  focus() { this.input.focus(); }

  _scroll() { this.output.scrollTop = this.output.scrollHeight; }
}

window.Terminal = Terminal;
