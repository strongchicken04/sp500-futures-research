"""RS leg by signal strength and by check time (day shift 2026-10-26, fixed
before results). On the first RS signal of the day (live rule): funded leg
+/-1.25% gross bp per trade, and sprint 0.20/0.30 resolved win rate.
Buckets: |rs| 0.15-0.25% / 0.25-0.40% / > 0.40%; check 10:00 / 11:00 / 13:00
/ 14:30. Four eras + 2026. A sizing-by-strength rule or dropping a check is
adopted only if the pattern holds in all four eras.
Usage: rs_buckets.py DATA_DIR
"""
from __future__ import annotations

import math
import statistics as st
import sys

sys.path.insert(0, "scripts")
from score_multi_feature import parse as parse_mf, first_signals, LEVELS as ML, bp  # noqa: E402

ERAS = (("2010-13", "2010", "2014", "_OLD"), ("2014-17", "2014", "2018", "_OLD"), ("2018-21", "2018", "2022", ""),
        ("2022-25", "2022", "2026", ""), ("2026", "2026", "2027", "26"))
BUCKETS = (("0.15-0.25", 0.0015, 0.0025), ("0.25-0.40", 0.0025, 0.004), (">0.40", 0.004, 9.0))


def cell(rows):
    big, ti, si = ML.index(125), ML.index(20), ML.index(30)
    if len(rows) < 5:
        return "  n<5"
    leg = [bp(r, s, big, big) for r, s in rows]
    sp = [bp(r, s, ti, si) for r, s in rows]
    h, m = sum(x == 20 for x in sp), sum(x == -30 for x in sp)
    t = st.mean(leg) / (st.pstdev(leg) / math.sqrt(len(leg))) if st.pstdev(leg) else 0
    return f"leg {st.mean(leg):+5.1f} bp (t{t:+4.1f}) win {h / max(1, h + m) * 100:4.1f}% n{len(rows):3d}"


def main():
    data = sys.argv[1]
    for lab, lo, hi, suf in ERAS:
        sig = {d: v for d, v in first_signals(parse_mf(f"{data}/MFEAT{suf}_tags.txt"), lambda r: 1 if (r["rs"] > 0.0015 and r["vwapd"] > 0) else
                                             (-1 if (r["rs"] < -0.0015 and r["vwapd"] < 0) else 0)).items() if lo <= d < hi}
        print(f"--- {lab}")
        for name, a, b in BUCKETS:
            print(f"   |rs| {name:<10} " + cell([v for v in sig.values() if a < abs(v[0]["rs"]) <= b]))
        for hm in (600, 660, 780, 870):
            print(f"   check {hm // 60:02d}:{hm % 60:02d}      " + cell([v for v in sig.values() if v[0]["hm"] == hm]))


if __name__ == "__main__":
    main()
