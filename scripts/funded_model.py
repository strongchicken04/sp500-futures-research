"""Funded LucidFlex 50K account model, corrected (night shift 2026-10-23/24).
Use this for every funded question from now on.

Fixes against mc_book / timed_book / funded_sizing:
  1. Calendar = every RTH day (book-trade days only skipped ~21% of days).
  2. Payout needs five days with >= $150 profit in the cycle (count resets
     after a payout) - LucidFlex rule per third-party summaries 2026-10.
  3. A payout WITHDRAWS $2,000 from the balance; profit above +$4,000 stays
     on the account (mc_book reset the balance to +$2,000 and dropped it).
Rules: $2,000 EOD-trailing drawdown (intraday equity checked after every
trade in exit order) that locks at +$100 once the balance clears +$2,100;
payout when profit >= trig (default $4,000) withdrawing amt (default $2,000),
owner gets 90%; a bust costs a new evaluation ($265, 10 trading days).

API:
  day lists: days = [ {"book": [usd per 1 MNQ, exit order], "rs": sig, "vw": sig} ]
  choose(day, st) -> list of usd for that day; st = dict(pnl, peak, line,
       pdays, pays) at the start of the day
  run_path(days, choose) -> cash over the path (eval lag at the start)
  first_payout(days, choose) -> (reached?, days) from day 0
  bootstrap(n_days, trials, seed) -> list of index paths (24 months, 20-day blocks)
"""
from __future__ import annotations

import random

# A bust buys a new evaluation: RS sprint on one account with the intraday
# drawdown (guardrail 6d, 2026-10-25): 12.4 / 8.1 days, $285 / $241 in
# 2018-21 / 2022-25 -> 10 days, $265 (was 11 days, $180 before the fix).
EVAL_DAYS, EVAL_COST, HORIZON, BLOCK = 10, 265.0, 504, 20


def run_path(days, choose, first_only=False, trig=4000.0, amt=2000.0, stats=None):
    t, cash = (0 if first_only else EVAL_DAYS), -EVAL_COST
    st = {"pnl": 0.0, "peak": 0.0, "pdays": 0, "pays": 0}
    while t < len(days):
        st["line"] = 100.0 if st["peak"] >= 2100.0 else st["peak"] - 2000.0
        eq, bust = st["pnl"], False
        for usd in choose(days[t], st):
            eq += usd
            if eq <= st["line"]:
                bust = True
                break
        t += 1
        if bust:
            if first_only:
                return False, t
            if stats is not None:
                stats.append(st["pays"])
            cash -= EVAL_COST
            t += EVAL_DAYS
            st = {"pnl": 0.0, "peak": 0.0, "pdays": 0, "pays": 0}
            continue
        if eq - st["pnl"] >= 150.0:
            st["pdays"] += 1
        st["pnl"] = eq
        st["peak"] = max(st["peak"], eq)
        if st["pnl"] >= trig and st["pdays"] >= 5 and st["peak"] >= 2100.0:
            if first_only:
                return True, t
            w = min(amt, st["pnl"] / 2.0)
            cash += 0.9 * w
            st["pnl"] -= w
            st["pdays"] = 0
            st["pays"] += 1
    if stats is not None:
        stats.append(st["pays"])
    return None if first_only else cash


def first_payout(days, choose):
    return run_path(days, choose, first_only=True)


def bootstrap(n_days, trials=4000, seed=1):
    rnd = random.Random(seed)
    out = []
    for _ in range(trials):
        idx = []
        while len(idx) < HORIZON:
            s = rnd.randrange(0, n_days - BLOCK)
            idx.extend(range(s, s + BLOCK))
        out.append(idx[:HORIZON])
    return out


def book(units=3):
    return lambda day, st: [u * units for u in day["book"]]
