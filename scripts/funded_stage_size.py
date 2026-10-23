"""Funded size by stage (time-aware sim): n MNQ per leg before the first payout
(f1) and after it (repeat payouts), grid {2,3,4} x {2,3,4}, no day stop.
Books: ORB+VG+Z and ORB+VG+Z+RS. Mean 24-month cash per account,
2018-21 | 2022-25 (choose on 2018-21).

Usage: funded_stage_size.py FIXED_DIR SCRATCH_DIR
"""
from __future__ import annotations

import sys

sys.path.insert(0, "scripts")
from timed_book import legs, days_for  # noqa: E402
from ladder_sim import outcomes  # noqa: E402
from funded_sizing import life  # noqa: E402


def main():
    tr = legs(sys.argv[1], sys.argv[2])
    cal_all = sorted({t[0] for t in tr})
    for bn, use in (("ORB+VG+Z", ("ORB", "VG", "Z")), ("ORB+VG+Z+RS", ("ORB", "VG", "Z", "RS"))):
        res = {}
        for lab, lo, hi in (("a", "0", "2022"), ("b", "2022", "9")):
            days = days_for(tr, [d for d in cal_all if lo <= d < hi], 1, 10 ** 9, use)
            for a in (2, 3, 4):
                f1 = outcomes(days, lambda room, a=a: (float(a), 1e9), window=300, start_pnl=0.0, target=4000.0, consistency=False)
                for b in (2, 3, 4):
                    rp = outcomes(days, lambda room, b=b: (float(b), 1e9), window=300, start_pnl=2000.0, target=4000.0, consistency=False, locked=100.0)
                    res.setdefault((a, b), {})[lab] = life(f1, rp)
        best = max(res, key=lambda k: res[k]["a"])
        print(f"== {bn}  (f1 size / repeat size: 2018-21 | 2022-25)")
        for k, v in sorted(res.items(), key=lambda kv: -kv[1]["a"]):
            print(f"   {k[0]} / {k[1]} MNQ   ${v['a']:8,.0f} | ${v['b']:8,.0f}{'   <- chosen on 2018-21' if k == best else ''}")


if __name__ == "__main__":
    main()
