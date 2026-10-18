"""Estimate how much of the shared 5-hour limit went to Claude Code, Cowork and chat.

Anthropic only reports one combined percentage. This keeps a history of that
percentage (our own /usage polls, plus the samples the Claude desktop app saves
in plan-usage-history.json) and, for every step where it went up, looks at what
was active on this PC in that time:

  only Claude Code replies   -> the whole rise counts as Claude Code
  only Cowork replies        -> the whole rise counts as Cowork
  both                       -> split by their weighted token use
  neither                    -> chat (or anything else: phone, browser, other PCs)

It is a guess: chat that happens at the same moment as Claude Code is counted
as Claude Code, and the percentage moves in whole steps.
"""

import json
import time
from pathlib import Path

STATE = Path.home() / '.local' / 'state' / 'clawd-usage' / 'session-history.json'
DESKTOP = Path.home() / '.config' / 'Claude' / 'plan-usage-history.json'
KEEP_SECONDS = 2 * 86400
SOURCES = ('all', 'code', 'cowork', 'chat')
TITLES = {'all': 'All of Claude', 'code': 'Claude Code', 'cowork': 'Cowork', 'chat': 'Chat & other'}
SHORT = {'all': 'All', 'code': 'Code', 'cowork': 'Cowork', 'chat': 'Chat'}


class Split:
    def __init__(self):
        self.samples = {}          # unix seconds -> session percent
        self.desktop_mtime = 0
        try:
            for t, p in json.loads(STATE.read_text()):
                self.samples[float(t)] = float(p)
        except Exception:
            pass

    def add(self, pct, t=None):
        self.samples[t or time.time()] = float(pct)
        self._trim_and_save()

    def _read_desktop(self):
        """Pull the desktop app's 15-minute samples ('fh' = five-hour percent)."""
        try:
            mt = DESKTOP.stat().st_mtime
            if mt == self.desktop_mtime:
                return
            self.desktop_mtime = mt
            for x in json.loads(DESKTOP.read_text()).get('samples', []):
                fh = (x.get('u') or {}).get('fh')
                if fh is not None and x.get('t'):
                    self.samples.setdefault(x['t'] / 1000.0, float(fh))
        except Exception:
            pass

    def _trim_and_save(self):
        cut = time.time() - KEEP_SECONDS
        self.samples = {t: p for t, p in self.samples.items() if t >= cut}
        try:
            STATE.parent.mkdir(parents=True, exist_ok=True)
            tmp = STATE.with_suffix('.tmp')
            tmp.write_text(json.dumps(sorted(self.samples.items())))
            tmp.replace(STATE)
        except OSError:
            pass

    def estimate(self, start, now, current, code, cowork):
        """{'all', 'code', 'cowork', 'chat'} percent of the window that began at `start`."""
        self._read_desktop()
        pts = [(start, 0.0)] + sorted((t, p) for t, p in self.samples.items() if start < t < now)
        pts.append((now, float(current)))
        skip = cowork.ids()
        r = {'all': float(current), 'code': 0.0, 'cowork': 0.0, 'chat': 0.0}
        prev_t, prev_p = pts[0]
        for t, p in pts[1:]:
            d = p - prev_p
            if d > 0:
                wc = code.weight(prev_t, t, skip)
                wk = cowork.weight(prev_t, t)
                if wc + wk <= 0:
                    r['chat'] += d
                else:
                    r['code'] += d * wc / (wc + wk)
                    r['cowork'] += d * wk / (wc + wk)
            # Samples can dip (rounding, another source lagging); keep the high mark.
            prev_p = max(prev_p, p)
            prev_t = t
        # Rounding from the dips above can leave the parts above the real total.
        total = r['code'] + r['cowork'] + r['chat']
        if total > r['all'] > 0:
            for k in ('code', 'cowork', 'chat'):
                r[k] *= r['all'] / total
        return r
