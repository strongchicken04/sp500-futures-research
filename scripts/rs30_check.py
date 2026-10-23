"""Independent check of the RS sprint with a 0.30% stop: the rs_variants
exporter re-run with STP = 0.30% (RSVA30/RSVB30) against the original 0.40%
export (RSVA/RSVB). Live rule (NQ-ES > thr and VWAP side, 10:00/11:00/13:00/
14:30), thresholds 10-25 bp; size so the stop costs ~$1,900.

Usage: rs30_check.py SCRATCH_DIR
"""
from __future__ import annotations

import statistics as st
import sys

sys.path.insert(0, "scripts")
from prop_sim import Trade  # noqa: E402
from mixed_accounts import calendar_days  # noqa: E402
from final_lifecycle import flat  # noqa: E402
from ladder_sim import outcomes  # noqa: E402
from score_rs_variants import parse, signals, FIX4  # noqa: E402


def usd(px, x, stop):
    n = max(1, min(40, int(1900 / (px * stop * 2.0))))
    return (x / 1e4 * px - 0.5) * 2.0 * n - n


def main():
    sp = sys.argv[1]
    for lab, files, stop in (("stop 0.40%", ("RSVA", "RSVB"), 0.004), ("stop 0.30%", ("RSVA30", "RSVB30"), 0.003)):
        days = parse([f"{sp}/{f}_tags.txt" for f in files])
        cal = sorted(days)
        print(f"== {lab}")
        for thr in (10, 15, 20, 25):
            rule = lambda r, day, thr=thr: 1 if (r["es"] > thr and r["vw"] > 0) else (-1 if (r["es"] < -thr and r["vw"] < 0) else 0)
            sig = signals(days, FIX4, rule)
            out = []
            for lo, hi in (("0", "2022"), ("2022", "9")):
                trs = [Trade(d, usd(day["px"], r["L"] if s == 1 else r["S"], stop), "S") for d, (day, r, s) in sig.items() if lo <= d < hi]
                cc = [c for c in cal if lo <= c < hi]
                o = outcomes(calendar_days(trs, cc), flat(1, 1e6), window=200, start_pnl=0.0, target=3000.0, consistency=True)
                p = sum(1 for x, _ in o if x == "pass") / len(o)
                out.append(f"pass {p * 100:4.1f}%  days {st.mean(d for _, d in o) / p:5.1f}  fees ${90 / p:3.0f}")
            print(f"   thr {thr:2} bp   {out[0]}  |  {out[1]}")


if __name__ == "__main__":
    main()
