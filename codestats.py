"""Claude Code usage on this computer, from its local transcripts.

Every assistant reply in ~/.claude/projects/**/*.jsonl carries the API usage of
that request. Claude Code writes one line per content block, so the same
message id repeats; each id is counted once. Files are read incrementally:
only bytes added since the last scan are parsed.

This is NOT a share of your plan limit - Anthropic doesn't publish how tokens
map to the limit percentages - just what Claude Code on this machine did.
"""

import json
import threading
import time
from datetime import datetime
from pathlib import Path

PROJECTS = Path.home() / '.claude' / 'projects'
# Cowork runs Claude's agent inside the desktop app; its transcripts (same format) land here.
COWORK = Path.home() / '.config' / 'Claude' / 'local-agent-mode-sessions'
KEEP_SECONDS = 8 * 86400


def _ts(s):
    try:
        return datetime.fromisoformat(s.replace('Z', '+00:00')).timestamp()
    except Exception:
        return None


class CodeStats:
    def __init__(self, root=PROJECTS):
        self.root = root
        self.offsets = {}        # path -> bytes already parsed
        self.msgs = {}           # message id -> (ts, input, output, cache_write, cache_read)
        self.thread = None
        self.last_try = 0.0
        self.ready = False
        self.lock = threading.Lock()

    def due(self, interval):
        if self.thread and self.thread.is_alive():
            return False
        return time.time() - self.last_try >= interval

    def start(self):
        self.last_try = time.time()
        self.thread = threading.Thread(target=self._scan, daemon=True)
        self.thread.start()

    def _scan(self):
        cutoff = time.time() - KEEP_SECONDS
        found = {}
        try:
            files = list(self.root.rglob('*.jsonl')) if self.root.is_dir() else []
        except OSError:
            files = []
        for f in files:
            try:
                st = f.stat()
            except OSError:
                continue
            if st.st_mtime < cutoff:
                continue
            off = self.offsets.get(f, 0)
            if st.st_size < off:      # file was rewritten
                off = 0
            if st.st_size == off:
                continue
            try:
                with open(f, 'rb') as fh:
                    fh.seek(off)
                    data = fh.read()
            except OSError:
                continue
            # Only parse whole lines; a half-written last line is read next time.
            end = data.rfind(b'\n') + 1
            self.offsets[f] = off + end
            for line in data[:end].splitlines():
                if b'"usage"' not in line:
                    continue
                try:
                    j = json.loads(line)
                except ValueError:
                    continue
                m = j.get('message') or {}
                u = m.get('usage')
                mid = m.get('id') or j.get('requestId')
                ts = _ts(j.get('timestamp', ''))
                if not u or not mid or ts is None or ts < cutoff:
                    continue
                found[mid] = (ts, int(u.get('input_tokens') or 0), int(u.get('output_tokens') or 0),
                              int(u.get('cache_creation_input_tokens') or 0),
                              int(u.get('cache_read_input_tokens') or 0))
        with self.lock:
            self.msgs.update(found)
            for k in [k for k, v in self.msgs.items() if v[0] < cutoff]:
                del self.msgs[k]
        self.ready = True

    def since(self, t0):
        """{'requests', 'input', 'output', 'cacheWrite', 'cacheRead'} for replies after t0."""
        r = {'requests': 0, 'input': 0, 'output': 0, 'cacheWrite': 0, 'cacheRead': 0}
        with self.lock:
            for ts, i, o, cw, cr in self.msgs.values():
                if ts >= t0:
                    r['requests'] += 1
                    r['input'] += i
                    r['output'] += o
                    r['cacheWrite'] += cw
                    r['cacheRead'] += cr
        return r


    def weight(self, t0, t1, skip=()):
        """Rough cost of the replies in (t0, t1], in input-token equivalents.

        Weighted like API prices: output 5x, cache writes 1.25x, cache reads 0.1x.
        Ids in `skip` are left out (so a reply seen by two readers counts once).
        """
        w = 0.0
        with self.lock:
            for mid, (ts, i, o, cw, cr) in self.msgs.items():
                if t0 < ts <= t1 and mid not in skip:
                    w += i + 5 * o + 1.25 * cw + 0.1 * cr
        return w

    def ids(self):
        with self.lock:
            return set(self.msgs)


def fmt_tokens(n):
    if n >= 1_000_000:
        return f'{n / 1_000_000:.1f}M'
    if n >= 1_000:
        return f'{n / 1_000:.0f}k'
    return str(n)
