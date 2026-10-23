"""Expected income per funded seat with the recommended book (VG + Z + RS, flat
3), from the paired block bootstrap: mean / median / 10th-90th percentile of
24-month cash (evaluations paid, $1,800 per payout) and the share of seats that
end below zero, 2018-21 and 2022-25; plus the same for today's book with ORB.
Usage: income.py DATA_DIR
"""
from __future__ import annotations

import sys

sys.path.insert(0, "scripts")
import gate_check as G  # noqa: E402
from mc_book import compare  # noqa: E402
from mc_runs import sized  # noqa: E402


def pct(v, q):
    v = sorted(v)
    return v[int(q * (len(v) - 1))]


def main():
    tr = G.build(sys.argv[1], set())
    cal_all = sorted({t[0] for t in tr})
    for lo, hi, lab in (("0", "2022", "2018-21"), ("2022", "9", "2022-25")):
        cal = [d for d in cal_all if lo <= d < hi]
        res = compare({"recommended (no ORB)": sized(tr, {"VG": 3, "Z": 3, "RS": 3}),
                       "today (with ORB)": sized(tr, {"ORB": 3, "VG": 3, "Z": 3, "RS": 3})}, cal, trials=4000, seed=137)
        for k, v in res.items():
            m = sum(v) / len(v)
            print(f"{lab} {k:<22} mean ${m:7,.0f} (${m / 24:5,.0f}/month), median ${pct(v, .5):7,.0f}, "
                  f"p10 ${pct(v, .1):7,.0f}, p90 ${pct(v, .9):7,.0f}, below zero {sum(x < 0 for x in v) / len(v) * 100:.0f}%")


if __name__ == "__main__":
    main()
