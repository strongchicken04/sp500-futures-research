"""After the first sprint loss: keep trading the same account (about $100 of
drawdown left, so the next loss busts) or abandon it and start a new $90
evaluation the next trading day? RS sprint (0.20/0.30) and 09:31 sprint
(0.25/0.40). Expected trading days to a pass and fees, from every start day.
Simplified daily model matching the sprint: one trade a day, pass at +$3,000
with best day <= 50% of profit, bust at -$2,000 EOD trailing (locks at +$100).

Usage: sprint_reset.py SCRATCH_DIR
"""
from __future__ import annotations

import statistics as st
import sys

sys.path.insert(0, "scripts")
from score_multi_feature import parse as parse_mf, first_signals, LEVELS  # noqa: E402
from rs_sprint_shape import usd as rs_usd  # noqa: E402
from bias_sprint import build  # noqa: E402
from t931_shape import usd as t_usd  # noqa: E402

FEE = 90.0


def attempt(seq, i, reset):
    """From day i: ('pass'|'bust'|'abandon'|'end', days used)."""
    pnl, peak, best, k = 0.0, 0.0, 0.0, 0
    while i + k < len(seq):
        x = seq[i + k]
        k += 1
        if x is None:
            continue
        pnl += x
        best = max(best, x)
        line = min(peak - 2000.0, 100.0)
        if pnl <= line:
            return "bust", k
        if pnl >= 3000.0 and best <= 0.5 * pnl:
            return "pass", k
        if reset and x < 0:
            return "abandon", k
        peak = max(peak, pnl)
    return "end", k


def run(seq, reset):
    days, fees = [], []
    for s in range(len(seq) - 150):
        t, n = s, 0
        while t < len(seq):
            res, k = attempt(seq, t, reset)
            n += 1
            t += k
            if res == "pass":
                days.append(t - s)
                fees.append(n * FEE)
                break
            if res == "end":
                break
    return st.mean(days), st.mean(fees)


def main():
    sp = sys.argv[1]
    rows = parse_mf(f"{sp}/MFEAT_tags.txt")
    rs = first_signals(rows, lambda r: 1 if (r["rs"] > 0.0015 and r["vwapd"] > 0) else
                       (-1 if (r["rs"] < -0.0015 and r["vwapd"] < 0) else 0))
    t9 = {r["date"]: t_usd(r, 1 if f["sma50"] > 0 else -1, 25, 40) for r, f in build(sp)}
    cal = sorted({r["date"] for r in rows})
    S = {"RS 0.20/0.30": {d: rs_usd(r, s, LEVELS.index(20), LEVELS.index(30)) for d, (r, s) in rs.items()},
         "09:31 0.25/0.40": t9}
    for name, m in S.items():
        print(f"== {name}")
        for lab, lo, hi in (("2018-21", "0", "2022"), ("2022-25", "2022", "9")):
            seq = [m.get(d) for d in cal if lo <= d < hi]
            dc, fc = run(seq, False)
            dr, fr = run(seq, True)
            print(f"   {lab}: keep trading after a loss {dc:5.1f} days ${fc:4.0f}   |   new evaluation after a loss {dr:5.1f} days ${fr:4.0f}")


if __name__ == "__main__":
    main()
