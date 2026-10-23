"""Group 7 (fixed 2026-10-23 before results): intraday compression.
  OR_NARROW  the 09:30-10:00 range is in the lowest third of the prior 20
             sessions' 09:30-10:00 ranges -> first 5-min close beyond it from
             10:00 -> go with it; stop at the other side; flat 15:55.
  OR_MID / OR_WIDE  the same rule in the middle / top third (controls).
  NR4 & OR_NARROW  both compressions on the same day.
Usage: or_width_lab.py DATA_DIR
"""
from __future__ import annotations

import sys

sys.path.insert(0, "scripts")
import level_lab as L  # noqa: E402


def brk(d, p):
    b = d["bars"]
    h, lo = max(x[1] for x in b[:6]), min(x[2] for x in b[:6])
    for i in range(6, L.LAST_ENTRY + 1):
        c = b[i][3]
        if c > h or c < lo:
            s = 1 if c > h else -1
            return s, L.run(b, i, s, c, lo if s == 1 else h)
    return None


def main():
    days = L.load(sys.argv[1])
    for n, d in enumerate(days):
        w = lambda x: (max(y[1] for y in x["bars"][:6]) - min(y[2] for y in x["bars"][:6])) / x["bars"][0][0]
        d["orw"] = None
        if n >= 20:
            prev = sorted(w(days[k]) for k in range(n - 20, n))
            x = w(d)
            d["orw"] = "narrow" if x <= prev[6] else "wide" if x >= prev[13] else "mid"
        rng = [days[j]["hi"] - days[j]["lo"] for j in range(max(0, n - 4), n)]
        d["nr4"] = n >= 4 and rng[-1] == min(rng)
    R = {"OR_NARROW": lambda d, p: brk(d, p) if d["orw"] == "narrow" else None,
         "OR_MID": lambda d, p: brk(d, p) if d["orw"] == "mid" else None,
         "OR_WIDE": lambda d, p: brk(d, p) if d["orw"] == "wide" else None,
         "NR4 & OR_NARROW": lambda d, p: brk(d, p) if d["orw"] == "narrow" and d["nr4"] else None}
    for name, fn in R.items():
        ts = L.trades(days, fn)
        a = [t["pts"] for t in ts if t["date"] < "2022"]
        b = [t["pts"] for t in ts if t["date"] >= "2022"]
        yrs = sorted({t["date"][:4] for t in ts})
        by = " ".join(f"{y[2:]}:{sum(t['pts'] for t in ts if t['date'][:4] == y):+.0f}" for y in yrs)
        print(f"{name:<16} 2018-21 {L.stat(a)} | 2022-25 {L.stat(b)}\n{'':<16} years {by}\n")


if __name__ == "__main__":
    main()
