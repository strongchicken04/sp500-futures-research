"""Account-B sprint candidates (fixed 2026-10-23 before results): one trade a day,
direction known at the entry time, bracket 0.25% / 0.40% (random-walk win of
resolved trades 61.5%) and 0.20% / 0.30% (60.0%). Measured in four eras on the
cond-bracket exports (CBA_OLD 2010-17, CBA 2018-25):
  MOM30   10:00, sign of 09:30 open -> 10:00
  VWAP10  10:00, side of the session VWAP
  GAPGO   10:00, sign of the gap (09:30 open vs prior close)
  GAPFADE 10:00, against the gap
  PDOUT   10:00, above the prior day high -> long, below the low -> short
  MOM60   10:30, sign of 09:30 open -> 10:30
  TREND   10:00, 50-day trend (as the 09:31 sprint, later entry)
Usage: b_sprint_lab.py DATA_DIR
"""
from __future__ import annotations

import statistics as st
import sys

sys.path.insert(0, "scripts")
from score_cond_bracket import parse, LEVELS  # noqa: E402

ERAS = (("2010-13", "2010", "2014"), ("2014-17", "2014", "2018"), ("2018-21", "2018", "2022"), ("2022-25", "2022", "2026"))
BR = ((25, 40, 40 / 65), (20, 30, 30 / 50))
sgn = lambda x: 1 if x > 0 else -1 if x < 0 else 0


def rows_by(data):
    out = {}
    for f in ("CBA_OLD", "CBA"):
        for r in parse([f"{data}/{f}_tags.txt"]):
            out.setdefault(r["type"], []).append(r)
    return out


def trend_map(t931):
    closes = {r["date"]: r["pc"] for r in t931}
    dates = sorted(closes)
    m = {}
    for i, d in enumerate(dates):
        if i >= 50:
            m[d] = sgn(closes[d] / st.mean(closes[dates[j]] for j in range(i - 49, i + 1)) - 1)
    return m


RULES = {
    "MOM30": ("T1000", lambda r, tm: sgn(r["e"] - r["o930"])),
    "VWAP10": ("T1000", lambda r, tm: sgn(r["e"] - r["vwap"])),
    "GAPGO": ("T1000", lambda r, tm: sgn(r["o930"] - r["pc"])),
    "GAPFADE": ("T1000", lambda r, tm: -sgn(r["o930"] - r["pc"])),
    "PDOUT": ("T1000", lambda r, tm: 1 if r["e"] > r["pdh"] else -1 if r["e"] < r["pdl"] else 0),
    "MOM60": ("T1030", lambda r, tm: sgn(r["e"] - r["o930"])),
    "TREND": ("T1000", lambda r, tm: tm.get(r["date"], 0)),
}


def resolved(rows, fn, tm, ti, si):
    h = s_ = 0
    for r in rows:
        d = fn(r, tm)
        if not d:
            continue
        fav, adv = (r["up"], r["dn"]) if d == 1 else (r["dn"], r["up"])
        t, sl = fav[ti], adv[si]
        if t >= 0 and (sl < 0 or t < sl):
            h += 1
        elif sl >= 0:
            s_ += 1
    return h, s_


def main():
    R = rows_by(sys.argv[1])
    tm = trend_map(R["T931"])
    for tp, sp, rnd in BR:
        ti, si = LEVELS.index(tp), LEVELS.index(sp)
        print(f"bracket +{tp / 100:.2f}% / -{sp / 100:.2f}% (random {rnd * 100:.1f}%): resolved win - random, pp (n)")
        for name, (typ, fn) in RULES.items():
            cells = []
            for lab, lo, hi in ERAS:
                rows = [r for r in R[typ] if lo <= r["date"] < hi]
                h, s_ = resolved(rows, fn, tm, ti, si)
                cells.append(f"{lab} {(h / (h + s_) - rnd) * 100:+5.1f} ({h + s_})" if h + s_ else f"{lab} n0")
            print(f"   {name:<8} " + " | ".join(cells))


if __name__ == "__main__":
    main()
