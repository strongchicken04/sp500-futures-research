"""Payout-aware funded sizing under the corrected model (night shift
2026-10-23/24, fixed before results). Calendar = all RTH days; payout needs
+$4,000 AND five days >= $150 profit in the cycle (income2.py). No-ORB book
(VG + Z + RS). Size per leg is chosen at the start of each day from the
account state (all legs that day use it):
  flat3   3 MNQ always (today)
  F2      2 MNQ when the payout is less than $1,000 away (old funded finisher)
  P2      2 MNQ once +$4,000 is reached but fewer than five profitable days
  P1      1 MNQ in the same state
  F2+P2   both
  L4      4 MNQ until the first payout, 3 after (more profitable days early)
Paired block bootstrap (24 months of 20-day blocks), 2018-21 / 2022-25, plus
2010-13 / 2014-17 (old_check.legs, gated; dollars ~4-6x smaller there, so few
paths reach a payout - direction only).
Usage: payout_size.py DATA_DIR
"""
from __future__ import annotations

import random
import statistics as st
import sys

sys.path.insert(0, "scripts")
import gate_check as G  # noqa: E402
from mc_runs import sized  # noqa: E402
from mc_book import EVAL_DAYS, EVAL_COST, PAYOUT, HORIZON, BLOCK  # noqa: E402
from score_cond_bracket import parse  # noqa: E402


def size_fn(name):
    def f(stage, pnl, pdays):
        n = 3
        if name in ("F2", "F2+P2") and pnl < 4000.0 and 4000.0 - pnl < 1000.0:
            n = 2
        if name in ("P2", "F2+P2") and pnl >= 4000.0 and pdays < 5:
            n = 2
        if name == "P1" and pnl >= 4000.0 and pdays < 5:
            n = 1
        if name == "L4":
            n = 4 if stage == "f1" else 3
        return n
    return f


def run_path(days, fn, first_only=False):
    t, cash = (0 if first_only else EVAL_DAYS), -EVAL_COST
    stage, pnl, peak, last_pay, pdays = "f1", 0.0, 0.0, -99, 0
    while t < len(days):
        line = 100.0 if stage == "rp" else min(peak - 2000.0, 100.0)
        n = fn(stage, pnl, pdays)
        eq, bust = pnl, False
        for usd in days[t]:
            eq += usd * n
            if eq <= line:
                bust = True
                break
        t += 1
        if bust:
            if first_only:
                return False, t
            cash -= EVAL_COST
            t += EVAL_DAYS
            stage, pnl, peak, pdays = "f1", 0.0, 0.0, 0
            continue
        if eq - pnl >= 150.0:
            pdays += 1
        pnl = eq
        peak = max(peak, pnl)
        if pnl >= 4000.0 and pdays >= 5 and (stage == "f1" or t - last_pay >= 5):
            if first_only:
                return True, t
            cash += PAYOUT
            last_pay = t
            stage, pnl, peak, pdays = "rp", 2000.0, 2000.0, 0
    return None if first_only else cash


NAMES = ("flat3", "F2", "P2", "P1", "F2+P2", "L4")


def main():
    data = sys.argv[1]
    import old_check as O
    tr = sized(G.build(data, set()), {"VG": 1, "Z": 1, "RS": 1})
    tr += sized([t[:5] for t in O.legs(data) if t[5]], {"VG": 1, "Z": 1, "RS": 1})
    full = sorted({r["date"] for f in ("CBA", "CBA_OLD") for r in parse([f"{data}/{f}_tags.txt"])})
    by = {}
    for t in tr:
        by.setdefault(t[0], []).append(t)
    for lo, hi, lab in (("2018", "2022", "2018-21"), ("2022", "2026", "2022-25"), ("2010", "2014", "2010-13"), ("2014", "2018", "2014-17")):
        days = [[t[3] for t in sorted(by.get(d, []), key=lambda t: t[2])] for d in full if lo <= d < hi]
        print(f"--- {lab}")
        rnd = random.Random(2024)
        paths = []
        for _ in range(4000):
            idx = []
            while len(idx) < HORIZON:
                s = rnd.randrange(0, len(days) - BLOCK)
                idx.extend(range(s, s + BLOCK))
            paths.append(idx[:HORIZON])
        base = None
        for name in NAMES:
            fn = size_fn(name)
            fp = [x for x in (run_path(days[s:], fn, True) for s in range(len(days) - 250)) if x]
            cash = [run_path([days[i] for i in p], fn) for p in paths]
            if base is None:
                base = cash
            d = [x - y for x, y in zip(cash, base)]
            print(f"   {name:<6} mean ${st.mean(cash):7,.0f} vs flat3 {st.mean(d):+6,.0f} (+/- {1.96 * st.pstdev(d) / len(d) ** 0.5:,.0f}) "
                  f"better/worse {sum(x > 0 for x in d) / len(d) * 100:3.0f}/{sum(x < 0 for x in d) / len(d) * 100:3.0f}% | "
                  f"first payout {sum(r for r, _ in fp) / len(fp) * 100:4.1f}%")


if __name__ == "__main__":
    main()
