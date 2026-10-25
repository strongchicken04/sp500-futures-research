"""Spread of days and fees to the first funded account with the intraday
drawdown (guardrail 6d; two_win_sprint INTRA), night shift 2026-10-25/26.
RS sprint 0.20/0.30 alone on one account (the recommendation) and the pair
RS (hedge guard) + 09:31 0.25/0.40: median, 80th / 95th percentile and worst
start, every start day of 2018-21, 2022-25 and the 2026 holdout.
Usage: eval_spread_intra.py DATA_DIR
"""
from __future__ import annotations

import sys

sys.path.insert(0, "scripts")
from score_multi_feature import parse as parse_mf, first_signals, LEVELS as ML  # noqa: E402
from score_cond_bracket import parse, LEVELS as CL  # noqa: E402
from b_sprint_lab import trend_map  # noqa: E402
from hedge_check import exit_min  # noqa: E402
from two_win_sprint import FEE, trade_pts, attempt_days  # noqa: E402


def pct(v, q):
    v = sorted(v)
    return v[min(len(v) - 1, int(q * len(v)))]


def line(lab, res):
    d, f = [x for x, _ in res], [y * FEE for _, y in res]
    return (f"   {lab:<22} days median {pct(d, .5):3d}, 80% {pct(d, .8):3d}, 95% {pct(d, .95):3d}, worst {max(d):3d} | "
            f"fees median ${pct(f, .5):4.0f}, 80% ${pct(f, .8):4.0f}, 95% ${pct(f, .95):5.0f}, worst ${max(f):5.0f} ({len(res)} starts)")


def main():
    data = sys.argv[1]
    for suf, lo, hi, lab, left in (("", "2018", "2022", "2018-21", 150), ("", "2022", "2026", "2022-25", 150), ("26", "2026", "2027", "2026 (Jan-Jul)", 40)):
        rs = {d: v for d, v in first_signals(parse_mf(f"{data}/MFEAT{suf}_tags.txt"), lambda r: 1 if (r["rs"] > 0.0015 and r["vwapd"] > 0) else
                                             (-1 if (r["rs"] < -0.0015 and r["vwapd"] < 0) else 0)).items() if lo <= d < hi}
        R = {}
        for r in parse([f"{data}/CBA{suf}_tags.txt"]):
            R.setdefault(r["type"], []).append(r)
        tm = trend_map(R["T931"])
        t9 = {r["date"]: (r, tm[r["date"]]) for r in R["T931"] if lo <= r["date"] < hi and tm.get(r["date"])}
        skip = set()
        for d, (ra, sa) in rs.items():
            if d in t9 and t9[d][1] != sa:
                rb, sb = t9[d]
                fav, adv = (rb["up"], rb["dn"]) if sb == 1 else (rb["dn"], rb["up"])
                if ra["hm"] < exit_min(571, fav, adv, CL.index(25), CL.index(40)):
                    skip.add(d)
        cal = sorted(d for d in {r["date"] for r in R["T931"]} if lo <= d < hi)
        A1 = [trade_pts(*rs[d], ML, 20, 30) if d in rs else None for d in cal]
        A = [trade_pts(*rs[d], ML, 20, 30) if d in rs and d not in skip else None for d in cal]
        B = [trade_pts(*t9[d], CL, 25, 40) if d in t9 else None for d in cal]
        single, pair = [], []
        for s0 in range(len(cal) - left):
            a1 = attempt_days(A1, s0, "two-win")
            if a1:
                single.append(a1)
            a, b = attempt_days(A, s0, "two-win"), attempt_days(B, s0, "two-win")
            if a and b:
                first = min(a[0], b[0])
                fees = (a[1] if a[0] <= first else 1 + a[1] * first // max(1, a[0])) + (b[1] if b[0] <= first else 1 + b[1] * first // max(1, b[0]))
                pair.append((first, fees))
        print(f"--- {lab}: days / fees to the first funded account (intraday drawdown)")
        print(line("RS alone (one account)", single))
        print(line("pair RS + 09:31", pair))


if __name__ == "__main__":
    main()
