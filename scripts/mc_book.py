"""Paired block-bootstrap lifecycle for funded book variants (day shift
2026-10-23). The lifecycle mean of timed_book/funded_sizing moves by $3-5k
when only the calendar changes (it walks one fixed history from every start
day). Here every trial is a fresh 24-month path of 20-day blocks drawn from
the half's history; all variants in a comparison use the SAME blocks, so the
difference between them is measured with little noise.

Account model as funded_sizing.life: a bust costs a new sprint evaluation
($180, 11 trading days); first payout at +$4,000 ($1,800 to the owner), then
the account restarts at +$2,000 with the drawdown locked at +$100 and pays
$1,800 at each +$4,000 again (at least 5 trading days apart); EOD trailing
drawdown $2,000 that locks at +$100; intraday equity checked after every
trade in exit order. No day stop.

API: compare(variants, cal, trials) where variants = {name: trades} and trades
are (date, entry_min, exit_min, usd, leg) already sized.
"""
from __future__ import annotations

import random
import statistics as st
from collections import defaultdict

EVAL_DAYS, EVAL_COST, PAYOUT, HORIZON, BLOCK = 11, 180.0, 1800.0, 504, 20


def day_lists(trades, cal):
    by = defaultdict(list)
    for t in trades:
        by[t[0]].append(t)
    return [[t[3] for t in sorted(by.get(d, []), key=lambda t: t[2])] for d in cal]


def run_path(days):
    """days: list of per-day trade USD lists (one 24-month path). Returns cash."""
    t, cash = EVAL_DAYS, -EVAL_COST
    stage, pnl, peak, last_pay = "f1", 0.0, 0.0, -99
    while t < len(days):
        line = 100.0 if stage == "rp" else min(peak - 2000.0, 100.0)
        eq = pnl
        bust = False
        for usd in days[t]:
            eq += usd
            if eq <= line:
                bust = True
                break
        t += 1
        if bust:
            cash -= EVAL_COST
            t += EVAL_DAYS
            stage, pnl, peak = "f1", 0.0, 0.0
            continue
        pnl = eq
        peak = max(peak, pnl)
        if pnl >= 4000.0 and (stage == "f1" or t - last_pay >= 5):
            cash += PAYOUT
            last_pay = t
            stage, pnl, peak = "rp", 2000.0, 2000.0
    return cash


def compare(variants, cal, trials=4000, seed=11):
    lists = {k: day_lists(v, cal) for k, v in variants.items()}
    n = len(cal)
    rnd = random.Random(seed)
    res = {k: [] for k in variants}
    for _ in range(trials):
        idx = []
        while len(idx) < HORIZON:
            s = rnd.randrange(0, n - BLOCK)
            idx.extend(range(s, s + BLOCK))
        idx = idx[:HORIZON]
        for k, L in lists.items():
            res[k].append(run_path([L[i] for i in idx]))
    return res


def summary(res, base):
    out = []
    b = res[base]
    for k, v in res.items():
        m = st.mean(v)
        if k == base:
            out.append(f"{k:<30} ${m:8,.0f}")
            continue
        d = [x - y for x, y in zip(v, b)]
        se = st.pstdev(d) / len(d) ** 0.5
        better = sum(x > 0 for x in d) / len(d)
        worse = sum(x < 0 for x in d) / len(d)
        out.append(f"{k:<30} ${m:8,.0f}   vs base {st.mean(d):+7,.0f} (+/- {1.96 * se:,.0f})  "
                   f"better / worse in {better * 100:.0f}% / {worse * 100:.0f}% of paths")
    return out
