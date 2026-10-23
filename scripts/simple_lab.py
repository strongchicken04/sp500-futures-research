"""Simple price-action rules on the BARS5 panel (group 6, fixed 2026-10-23 before
results). Same fills and costs as level_lab.py; flat 15:55.
  GAPGO    gap >= 0.5% (09:30 open vs prior 16:00 close); the first 5-min bar
           closes in the gap direction -> go with it at its close; stop at the
           first bar's other extreme.
  GAPFADE  gap 0.3-1.0%; the first 5-min bar closes against the gap -> fade at
           its close; target the prior close; stop at the first bar's extreme.
  INSIDE   prior session's range inside the one before (inside day); first
           5-min close beyond the prior high/low -> go with it; stop 0.15% back.
  NR7      prior session's range the smallest of the last 7; from 10:00 the
           first close beyond the 09:30-10:00 range -> go with it; stop at the
           other side of that range.
  BIGDAY   prior session moved >= 2% open->close; follow its direction at the
           10:00 close; stop 0.50%.
Usage: simple_lab.py DATA_DIR
"""
from __future__ import annotations

import sys

sys.path.insert(0, "scripts")
import level_lab as L  # noqa: E402


def gap(day, prev):
    return day["bars"][0][0] / prev["bars"][77][3] - 1.0 if len(prev["bars"]) > 77 else 0.0


def gapgo(day, prev):
    g = gap(day, prev)
    b = day["bars"]
    if abs(g) < 0.005:
        return None
    d = 1 if g > 0 else -1
    if d * (b[0][3] - b[0][0]) <= 0:
        return None
    return d, L.run(b, 0, d, b[0][3], b[0][2] if d == 1 else b[0][1])


def gapfade(day, prev):
    g = gap(day, prev)
    b = day["bars"]
    if not 0.003 <= abs(g) <= 0.010:
        return None
    d = -1 if g > 0 else 1
    if d * (b[0][3] - b[0][0]) <= 0:
        return None
    return d, L.run(b, 0, d, b[0][3], b[0][1] if d == -1 else b[0][2], prev["bars"][77][3])


def main():
    days = L.load(sys.argv[1])
    for n, d in enumerate(days):
        d["inside"] = n >= 2 and days[n - 1]["hi"] <= days[n - 2]["hi"] and days[n - 1]["lo"] >= days[n - 2]["lo"]
        rng = [days[k]["hi"] - days[k]["lo"] for k in range(max(0, n - 7), n)]
        d["nr7"] = n >= 7 and rng[-1] == min(rng)
        pb = days[n - 1]["bars"] if n else None
        d["prevmove"] = (pb[77][3] / pb[0][0] - 1.0) if pb and len(pb) > 77 else 0.0
    R = {
        "GAPGO": gapgo,
        "GAPFADE": gapfade,
        "INSIDE": lambda d, p: L.pdbrk(d, p, 0.0015) if d["inside"] else None,
        "NR7": lambda d, p: (lambda b, h, l: next(((1 if b[i][3] > h else -1, L.run(b, i, 1 if b[i][3] > h else -1, b[i][3], l if b[i][3] > h else h))
                                                  for i in range(6, L.LAST_ENTRY + 1) if b[i][3] > h or b[i][3] < l), None))(
            d["bars"], max(x[1] for x in d["bars"][:6]), min(x[2] for x in d["bars"][:6])) if d["nr7"] else None,
        "BIGDAY": lambda d, p: (lambda s: (s, L.run(d["bars"], 5, s, d["bars"][5][3], d["bars"][5][3] * (1 - s * 0.005))))(
            1 if d["prevmove"] > 0 else -1) if abs(d["prevmove"]) >= 0.02 else None,
    }
    for name, fn in R.items():
        ts = L.trades(days, fn)
        a = [t["pts"] for t in ts if t["date"] < "2022"]
        b = [t["pts"] for t in ts if t["date"] >= "2022"]
        yrs = sorted({t["date"][:4] for t in ts})
        by = " ".join(f"{y[2:]}:{sum(t['pts'] for t in ts if t['date'][:4] == y):+.0f}" for y in yrs)
        print(f"{name:<8} 2018-21 {L.stat(a)} | 2022-25 {L.stat(b)}\n{'':<8} years {by}\n")


if __name__ == "__main__":
    main()
