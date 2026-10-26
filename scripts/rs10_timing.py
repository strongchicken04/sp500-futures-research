"""RS leg only at the first check (RS10), timing check 6c (day shift
2026-10-26): the first-check edge must survive the checks shifted -5 / +5 min
(MFEAT*_M5 / _P5 exports: 09:55 / 10:05 first check). Funded leg +/-1.25%
gross bp of the first daily signal when it comes at the first check vs later.
Usage: rs10_timing.py DATA_DIR
"""
from __future__ import annotations

import math
import statistics as st
import sys

sys.path.insert(0, "scripts")
from score_multi_feature import parse as parse_mf, first_signals, LEVELS as ML, bp  # noqa: E402

ERAS = (("2010-13", "2010", "2014", "_OLD"), ("2014-17", "2014", "2018", "_OLD"), ("2018-21", "2018", "2022", ""), ("2022-25", "2022", "2026", ""))


def cell(v):
    if len(v) < 5:
        return "n<5"
    t = st.mean(v) / (st.pstdev(v) / math.sqrt(len(v))) if st.pstdev(v) else 0
    return f"{st.mean(v):+5.1f} bp (t{t:+4.1f}, n{len(v)})"


def main():
    data = sys.argv[1]
    big = ML.index(125)
    for shift in ("_M5", "", "_P5"):
        print(f"--- checks shifted {shift or 'live'}: first check | later checks")
        for lab, lo, hi, suf in ERAS:
            sig = {d: v for d, v in first_signals(parse_mf(f"{data}/MFEAT{suf}{shift}_tags.txt"), lambda r: 1 if (r["rs"] > 0.0015 and r["vwapd"] > 0) else
                                                 (-1 if (r["rs"] < -0.0015 and r["vwapd"] < 0) else 0)).items() if lo <= d < hi}
            first_hm = min(r["hm"] for r, _ in sig.values())
            a = [bp(r, s, big, big) for r, s in sig.values() if r["hm"] == first_hm]
            b = [bp(r, s, big, big) for r, s in sig.values() if r["hm"] != first_hm]
            print(f"   {lab} (first {first_hm // 60:02d}:{first_hm % 60:02d}): {cell(a)} | {cell(b)}")


if __name__ == "__main__":
    main()
