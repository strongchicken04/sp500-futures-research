"""When to request a payout on LucidFlex 50K (night shift 2026-10-23/24, fixed
before results). Third-party summaries (2026-10): a payout needs five days with
>= $150 profit in the cycle; the request is <= 50% of the profit, at most
$2,000, at least $500; split 90/10; drawdown $2,000 EOD trailing, locks at
+$100 once the balance clears +$2,100; no consistency rule when funded. The
owner's plan so far: withdraw $2,000 at +$4,000. Policies (withdrawals only
once the drawdown is locked, since the trail before the lock is unclear):
  4000/2000  at profit >= 4,000 withdraw 2,000 (today)
  3000/1500  at profit >= 3,000 withdraw half
  asap       at profit >= 2,100 withdraw min(2,000, half) as soon as eligible
  5000/2000  at profit >= 5,000 withdraw 2,000 (keeps a 2,900 cushion)
  6000/2000  at profit >= 6,000 withdraw 2,000
No-ORB book, flat 3, all RTH days, bust = new evaluation ($180, 11 days),
cash = 90% of withdrawals. Paired block bootstrap, 24 months. Also: share of
account lives with >= 5 payouts (LucidFlex may cap at 5 per account, then
moves the trader to a live account - not modelled).
Usage: payout_policy.py DATA_DIR
"""
from __future__ import annotations

import random
import statistics as st
import sys

sys.path.insert(0, "scripts")
import gate_check as G  # noqa: E402
from mc_runs import sized  # noqa: E402
from mc_book import EVAL_DAYS, EVAL_COST, HORIZON, BLOCK  # noqa: E402
from score_cond_bracket import parse  # noqa: E402

POL = {"4000/2000": (4000.0, 2000.0), "3000/1500": (3000.0, None), "asap": (2100.0, None),
       "5000/2000": (5000.0, 2000.0), "6000/2000": (6000.0, 2000.0)}


def run_path(days, pol):
    trig, amt = pol
    t, cash = EVAL_DAYS, -EVAL_COST
    pnl, peak, pdays, pays, lives5 = 0.0, 0.0, 0, 0, 0
    lives = 1
    while t < len(days):
        locked = peak >= 2100.0
        line = 100.0 if locked else peak - 2000.0
        eq, bust = pnl, False
        for usd in days[t]:
            eq += usd
            if eq <= line:
                bust = True
                break
        t += 1
        if bust:
            cash -= EVAL_COST
            t += EVAL_DAYS
            lives5 += pays >= 5
            lives += 1
            pnl, peak, pdays, pays = 0.0, 0.0, 0, 0
            continue
        if eq - pnl >= 150.0:
            pdays += 1
        pnl = eq
        peak = max(peak, pnl)
        if peak >= 2100.0 and pdays >= 5 and pnl >= trig:
            w = min(2000.0, pnl / 2.0) if amt is None else amt
            if w >= 500.0:
                cash += 0.9 * w
                pnl -= w
                pdays = 0
                pays += 1
    lives5 += pays >= 5
    return cash, lives5 / lives


def main():
    data = sys.argv[1]
    tr = sized(G.build(data, set()), {"VG": 3, "Z": 3, "RS": 3})
    full = sorted({r["date"] for r in parse([f"{data}/CBA_tags.txt"])})
    by = {}
    for t in tr:
        by.setdefault(t[0], []).append(t)
    for lo, hi, lab in (("2018", "2022", "2018-21"), ("2022", "2026", "2022-25")):
        days = [[t[3] for t in sorted(by.get(d, []), key=lambda t: t[2])] for d in full if lo <= d < hi]
        rnd = random.Random(777)
        paths = []
        for _ in range(4000):
            idx = []
            while len(idx) < HORIZON:
                s = rnd.randrange(0, len(days) - BLOCK)
                idx.extend(range(s, s + BLOCK))
            paths.append(idx[:HORIZON])
        print(f"--- {lab}")
        base = None
        for name, pol in POL.items():
            out = [run_path([days[i] for i in p], pol) for p in paths]
            cash = [c for c, _ in out]
            base = base or cash
            d = [x - y for x, y in zip(cash, base)]
            sv = sorted(cash)
            print(f"   {name:<10} mean ${st.mean(cash):7,.0f} p10 ${sv[len(sv) // 10]:7,.0f} vs today {st.mean(d):+6,.0f} "
                  f"(+/- {1.96 * st.pstdev(d) / len(d) ** 0.5:,.0f}) better/worse {sum(x > 0 for x in d) / len(d) * 100:3.0f}/"
                  f"{sum(x < 0 for x in d) / len(d) * 100:3.0f}% | lives with >= 5 payouts {st.mean(f for _, f in out) * 100:4.1f}%")


if __name__ == "__main__":
    main()
