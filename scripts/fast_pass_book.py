"""A one-trade-a-day 'fast pass' book from the best win-streak signals.

Each day the first of these to fire is traded (all NQ, all long, bracket
target 5 bp / stop 15 bp, so reward:risk 1:3 and a random-walk win rate of
75%):
    NZU  first half-hour close above the noise area, if the day opened
         0.25%+ above the prior close or the prior close is above its 200-day
         average
    T1100  11:00 ET, if the prior close is above its 200-day average and price
         is above VWAP
The rules were read off both 2018-2021 and 2022-2025 (the strongest families
in score_xmkt_streak / the streak ranking), so neither half is a clean
out-of-sample test; expect the live win rate to come in a few points lower.

Sizing: a win is worth W dollars and a loss 3 W (W = $400-$600), in MNQ,
capped at 40 MNQ (4 NQ), $1 cost per MNQ; with the cap, early years (NQ near
6,500) win less than W. The evaluation is simulated with the account rules
starting on every day in turn.
"""
from __future__ import annotations

import statistics as st
import sys

sys.path.insert(0, "scripts")
from prop_sim import Trade  # noqa: E402
from rescore_all import rvol  # noqa: E402
from mixed_accounts import calendar_days  # noqa: E402
from final_lifecycle import flat  # noqa: E402
from ladder_sim import outcomes  # noqa: E402
from score_cond_bracket import parse, add_daily, LEVELS  # noqa: E402

TI, SI = LEVELS.index(5), LEVELS.index(15)


def eligible(r):
    above = r["sma"] is not None and r["pc"] > r["sma"]
    if r["type"] == "NZU":
        return r["gap"] >= 0.0025 or above
    if r["type"] == "T1100":
        return above and r["e"] > r["vwap"]
    return False


def pts(r):
    t, s = r["up"][TI], r["dn"][SI]
    tp, sl = r["e"] * 5 / 1e4, r["e"] * 15 / 1e4
    if s >= 0 and (t < 0 or s <= t):
        return -sl - 0.25, tp
    if t >= 0:
        return tp, tp
    return max(-sl - 0.25, r["eod"]), tp


def main():
    sp = sys.argv[1]
    reg = rvol()
    rows = parse([f"{sp}/{x}_tags.txt" for x in ("CBA", "CBD")])
    add_daily(rows)
    rows = [r for r in rows if reg.get(r["date"], 9.0) < 0.30]
    cal = sorted({r["date"] for r in rows})
    first = {}
    for r in rows:
        if eligible(r) and (r["date"] not in first or r["hm"] < first[r["date"]]["hm"]):
            first[r["date"]] = r
    days = sorted(first)
    for lo, hi, lab in (("0", "2022", "2018-21"), ("2022", "9", "2022-25")):
        v = [pts(first[d])[0] for d in days if lo <= d < hi]
        n = len([c for c in cal if lo <= c < hi])
        print(f"{lab}: {len(v)} trades on {n} days ({len(v)/n*100:.0f}% of days), "
              f"WR {sum(1 for x in v if x > 0)/len(v)*100:.1f}% (random 75%)")
    print()
    for w in (400.0, 500.0, 600.0):
        trades = []
        for d in days:
            p, tp = pts(first[d])
            n = max(1, min(40, round(w / (tp * 2.0))))
            trades.append(Trade(d, p * 2.0 * n - 1.0 * n, "F"))
        out = []
        for lo, hi in (("0", "2022"), ("2022", "9")):
            ts = [t for t in trades if lo <= t.date < hi]
            cc = [c for c in cal if lo <= c < hi]
            o = outcomes(calendar_days(ts, cc), flat(1, 1e6), window=160, start_pnl=0.0, target=3000.0, consistency=True)
            ps = sum(1 for x, _ in o if x == "pass") / len(o) * 100
            md = sorted(dd for x, dd in o if x == "pass")
            out.append(f"pass {ps:4.1f}% in {md[len(md)//2] if md else 0:3} trading days")
        print(f"win ${w:.0f} / loss ${3*w:.0f}:  2018-21 {out[0]}  |  2022-25 {out[1]}")


if __name__ == "__main__":
    main()
