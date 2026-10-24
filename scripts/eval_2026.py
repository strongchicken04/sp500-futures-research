"""Evaluation sprints in the 2026 holdout (Jan - Jul 24): days and fees to a
pass from every start day (two-win sizing with the exact finisher), single
accounts RS / 09:31 / VWAP10 and the pair RS + 09:31 with the hedge guard.
Starts need >= 40 trading days of data left (day shift 2026-10-24).
Usage: eval_2026.py DATA_DIR
"""
from __future__ import annotations

import statistics as st
import sys

sys.path.insert(0, "scripts")
from score_multi_feature import parse as parse_mf, first_signals, LEVELS as ML  # noqa: E402
from score_cond_bracket import parse, LEVELS as CL  # noqa: E402
from b_sprint_lab import trend_map, sgn  # noqa: E402
from hedge_check import exit_min  # noqa: E402
from two_win_sprint import trade_pts, attempt_days, FEE  # noqa: E402

LO = "2026"


def main():
    data = sys.argv[1]
    rs = first_signals(parse_mf(f"{data}/MFEAT26_tags.txt"), lambda r: 1 if (r["rs"] > 0.0015 and r["vwapd"] > 0) else
                       (-1 if (r["rs"] < -0.0015 and r["vwapd"] < 0) else 0))
    R = {}
    for r in parse([f"{data}/CBA26_tags.txt"]):
        R.setdefault(r["type"], []).append(r)
    tm = trend_map(R["T931"])
    t9 = {r["date"]: (r, tm[r["date"]]) for r in R["T931"] if tm.get(r["date"])}
    vw = {r["date"]: (r, sgn(r["e"] - r["vwap"])) for r in R["T1000"] if sgn(r["e"] - r["vwap"])}
    cal = sorted(d for d in {r["date"] for r in R["T931"]} if d >= LO)
    skip = set()
    for d, (ra, sa) in rs.items():
        if d in t9 and t9[d][1] != sa:
            rb, sb = t9[d]
            fav, adv = (rb["up"], rb["dn"]) if sb == 1 else (rb["dn"], rb["up"])
            if ra["hm"] < exit_min(571, fav, adv, CL.index(25), CL.index(40)):
                skip.add(d)
    def ser(sig, lv, tp, sp, sk=()):
        return [trade_pts(sig[d][0], sig[d][1], lv, tp, sp) if d in sig and d not in sk else None for d in cal]
    S = {"RS": ser(rs, ML, 20, 30), "RSg": ser(rs, ML, 20, 30, skip), "09:31": ser(t9, CL, 25, 40), "VWAP10": ser(vw, CL, 25, 40)}
    print(f"2026 holdout {cal[0]}..{cal[-1]} ({len(cal)} days): days to a pass / fees, starts with >= 40 days left")
    for name in ("RS", "09:31", "VWAP10"):
        res = [x for x in (attempt_days(S[name], s, "two-win") for s in range(len(cal) - 40)) if x]
        n = len(cal) - 40
        print(f"   {name:<7} passed {len(res)}/{n} starts, mean {st.mean(d for d, _ in res):4.1f} days, fees ${st.mean(e for _, e in res) * FEE:4.0f}")
    res = []
    for s in range(len(cal) - 40):
        a = attempt_days(S["RSg"], s, "two-win")
        b = attempt_days(S["09:31"], s, "two-win")
        f = min(x[0] for x in (a, b) if x) if (a or b) else None
        if f:
            fees = sum((x[1] if x and x[0] <= f else 1 + (x[1] * f // max(1, x[0])) if x else 2) for x in (a, b))
            res.append((f, fees))
    print(f"   pair RS + 09:31 (guard): first funded in {st.mean(d for d, _ in res):4.1f} days, fees ~${st.mean(e for _, e in res) * FEE:4.0f} ({len(res)} starts)")


if __name__ == "__main__":
    main()
