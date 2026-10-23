"""ICT-style rules popular with prop traders, on the BARS5 v2 panel (B2A/B2B:
5-min NQ RTH bars + Asia / London ranges). Fixed before results (2026-10-23):

  SB      Silver Bullet: the first 5-min fair value gap fully inside 10:00-11:00
          (bullish: high of bar k-2 < low of bar k; bearish mirror); enter on
          the first retrace to the gap's near edge by 11:00 (limit; the fill
          bar is checked for the stop); stop at the far end of bar k-2;
          target 1.5 / 2 / 3 R; flat 15:55.
  LONSWP  London high/low (02:00-05:00 ET) swept 09:30-11:30, then a 5-min
          close back inside -> fade; stop 2 pt beyond the extreme so far;
          target the other side of the London range; flat 15:55.
  ASIASWP the same with the Asia range (18:00-24:00 ET).
  PWSWP   prior week high/low (RTH and overnight) swept by 14:00, then a close
          back inside -> fade; stop 2 pt beyond the extreme; flat 15:55.
  PWBRK   first 5-min close beyond the prior week high/low (opened inside) ->
          go with it; stop 0.15% back inside the level; flat 15:55.
Fills and costs as level_lab.py.

Usage: ict_lab.py DATA_DIR
"""
from __future__ import annotations

import datetime as dt
import math
import os
import statistics as st
import sys

sys.path.insert(0, "scripts")
import level_lab as L  # noqa: E402


def load(data):
    L.NAMES = ("B2A", "B2B")
    days = L.load(data)
    extra = {}
    for nm in L.NAMES:
        p = os.path.join(data, f"{nm}_tags.txt")
        for raw in open(p):
            f = raw.strip().split(",")
            if f[0] == "H" and len(f) >= 16:
                extra[f[1]] = tuple(float(x) for x in f[12:16])
    for d in days:
        k = d["date"].replace("-", "")
        d["ah"], d["al"], d["lh"], d["ll"] = extra.get(k, (0, 0, 0, 0))
    # prior ISO week high/low from RTH and overnight extremes
    wk = {}
    for d in days:
        y, w, _ = dt.date.fromisoformat(d["date"]).isocalendar()
        hi = max(d["hi"], d["onh"] or d["hi"])
        lo = min(d["lo"], d["onl"] or d["lo"])
        a = wk.setdefault((y, w), [hi, lo, d["exp"]])
        a[0], a[1] = max(a[0], hi), min(a[1], lo)
    keys = sorted(wk)
    prevw = {keys[i]: wk[keys[i - 1]] for i in range(1, len(keys))}
    for d in days:
        y, w, _ = dt.date.fromisoformat(d["date"]).isocalendar()
        p = prevw.get((y, w))
        d["pwh"], d["pwl"] = (p[0], p[1]) if p and p[2] == d["exp"] else (None, None)
    return days


def sb(day, prev, rr):
    b = day["bars"]
    for k in range(8, 18):                       # bars k-2..k inside 10:00-11:00 (indices 6..17)
        up = b[k - 2][1] < b[k][2]
        dn = b[k - 2][2] > b[k][1]
        if not (up or dn):
            continue
        d = 1 if up else -1
        edge = b[k][2] if up else b[k][1]
        stop = b[k - 2][2] if up else b[k - 2][1]
        for j in range(k + 1, 18):
            o, h, l, c, _ = b[j]
            if (d == 1 and l <= edge) or (d == -1 and h >= edge):
                e = min(edge, o) if d == 1 else max(edge, o)
                risk = abs(e - stop)
                if risk <= 0:
                    return None
                return d, L.run(b, j, d, e, stop, e + d * rr * risk, check_entry_bar=True)
        return None                              # first gap only
    return None


def sweep_range(day, hi_lvl, lo_lvl, last, target_other=True):
    b = day["bars"]
    if not hi_lvl or not lo_lvl or not (lo_lvl < b[0][0] < hi_lvl):
        return None
    above = below = False
    ext_hi, ext_lo = -1e18, 1e18
    for i in range(0, last + 1):
        o, h, l, c, _ = b[i]
        ext_hi, ext_lo = max(ext_hi, h), min(ext_lo, l)
        above = above or h > hi_lvl
        below = below or l < lo_lvl
        if above and c < hi_lvl:
            return -1, L.run(b, i, -1, c, ext_hi + 2.0, lo_lvl if target_other and lo_lvl < c else None)
        if below and c > lo_lvl:
            return 1, L.run(b, i, 1, c, ext_lo - 2.0, hi_lvl if target_other and hi_lvl > c else None)
    return None


def pwbrk(day, prev):
    b = day["bars"]
    h, l = day["pwh"], day["pwl"]
    if h is None or not (l < b[0][0] < h):
        return None
    for i in range(0, L.LAST_ENTRY + 1):
        c = b[i][3]
        if c > h or c < l:
            d = 1 if c > h else -1
            lvl = h if d == 1 else l
            return d, L.run(b, i, d, c, lvl * (1 - d * 0.0015))
    return None


def rules():
    R = {f"SB {rr}R": (lambda d, p, rr=rr: sb(d, p, rr)) for rr in (1.5, 2.0, 3.0)}
    R["LONSWP"] = lambda d, p: sweep_range(d, d["lh"], d["ll"], 23)
    R["ASIASWP"] = lambda d, p: sweep_range(d, d["ah"], d["al"], 23)
    R["PWSWP"] = lambda d, p: sweep_range(d, d["pwh"], d["pwl"], 54, target_other=False)
    R["PWBRK"] = pwbrk
    return R


def main():
    days = load(sys.argv[1])
    print(f"sessions {len(days)}; with London levels {sum(1 for d in days if d['lh'])}, prior week {sum(1 for d in days if d['pwh'])}\n")
    for name, fn in rules().items():
        ts = L.trades(days, fn)
        a = [t["pts"] for t in ts if t["date"] < "2022"]
        b = [t["pts"] for t in ts if t["date"] >= "2022"]
        yrs = sorted({t["date"][:4] for t in ts})
        by = " ".join(f"{y[2:]}:{sum(t['pts'] for t in ts if t['date'][:4] == y):+.0f}" for y in yrs)
        print(f"{name:<9} 2018-21 {L.stat(a)} | 2022-25 {L.stat(b)}")
        print(f"{'':<9} years {by}\n")


if __name__ == "__main__":
    main()
