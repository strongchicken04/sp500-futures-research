"""RS signal combined with volume (owner 2026-10-26: "does it help to combine
the volume signal with another one?"; rules fixed before results).
For each RS signal (first of 10:00 / 11:00 / 13:00 / 14:30, live rule):
  rvol = volume of the RTH session up to the check / the 20-day mean volume
         over the same window (5-min panels)
Terciles of rvol fixed from 2018-21 (tuning era), applied to all eras.
Funded leg +/-1.25% gross bp and sprint 0.20/0.30 resolved win by tercile,
four eras + 2026. A volume filter is adopted only if the same tercile is the
best (or the worst) in all four eras.
Usage: rs_volume.py DATA_DIR
"""
from __future__ import annotations

import math
import statistics as st
import sys

sys.path.insert(0, "scripts")
import big_trades as B  # noqa: E402
from score_multi_feature import parse as parse_mf, first_signals, LEVELS as ML, bp  # noqa: E402

KEND = {600: 5, 660: 17, 780: 41, 870: 59}


def main():
    data = sys.argv[1]
    days = B.load(data)
    idx = {d: i for i, (d, _) in enumerate(days)}
    sig = {}
    for suf in ("_OLD", "", "26"):
        sig.update(first_signals(parse_mf(f"{data}/MFEAT{suf}_tags.txt"), lambda r: 1 if (r["rs"] > 0.0015 and r["vwapd"] > 0) else
                                 (-1 if (r["rs"] < -0.0015 and r["vwapd"] < 0) else 0)))
    rows = []
    for d, (r, s) in sig.items():
        if d not in idx or idx[d] < 20 or r["hm"] not in KEND:
            continue
        i, k = idx[d], KEND[r["hm"]]
        cur = sum(x[4] for x in days[i][1][:k + 1])
        avg = st.mean(sum(x[4] for x in days[j][1][:k + 1]) for j in range(i - 20, i))
        if avg > 0:
            rows.append((d, cur / avg, r, s))
    tune = sorted(v for d, v, _, _ in rows if "2018" <= d < "2022")
    q1, q2 = tune[len(tune) // 3], tune[2 * len(tune) // 3]
    print(f"rvol terciles from 2018-21: low < {q1:.2f} <= mid < {q2:.2f} <= high")
    big, ti, si = ML.index(125), ML.index(20), ML.index(30)
    for lab, lo, hi in B.ERAS:
        cells = []
        for name, a, b in (("low", 0, q1), ("mid", q1, q2), ("high", q2, 99)):
            sel = [(r, s) for d, v, r, s in rows if lo <= d < hi and a <= v < b]
            if len(sel) < 10:
                cells.append(f"{name} n<10")
                continue
            leg = [bp(r, s, big, big) for r, s in sel]
            sp = [bp(r, s, ti, si) for r, s in sel]
            h, m = sum(x == 20 for x in sp), sum(x == -30 for x in sp)
            t = st.mean(leg) / (st.pstdev(leg) / math.sqrt(len(leg)))
            cells.append(f"{name} leg {st.mean(leg):+5.1f} bp (t{t:+4.1f}) win {h / max(1, h + m) * 100:4.1f}% n{len(sel)}")
        print(f"--- {lab}: " + " | ".join(cells))


if __name__ == "__main__":
    main()
