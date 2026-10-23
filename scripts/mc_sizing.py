"""Size by cushion for the no-ORB funded book (VG + Z + RS), paired bootstrap
(2026-10-23, grid fixed in advance). Units = MNQ per leg as a function of the
room above the drawdown line (room = pnl - line, $2,000 at the start):
  flat 3 (base) | flat 2 | flat 4 | 2 until room >= $3,000 then 3 |
  3 until room >= $3,000 then 4 | 3, but 2 when room < $1,000
Usage: mc_sizing.py DATA_DIR
"""
from __future__ import annotations

import random
import statistics as st
import sys

sys.path.insert(0, "scripts")
import gate_check as G  # noqa: E402
import mc_book as M  # noqa: E402

SIZERS = {
    "flat 3": lambda room: 3, "flat 2": lambda room: 2, "flat 4": lambda room: 4,
    "2 -> 3 at room $3k": lambda room: 3 if room >= 3000 else 2,
    "3 -> 4 at room $3k": lambda room: 4 if room >= 3000 else 3,
    "3, 2 below room $1k": lambda room: 2 if room < 1000 else 3,
}


def run_path(days, sizer):
    t, cash = M.EVAL_DAYS, -M.EVAL_COST
    stage, pnl, peak, last_pay = "f1", 0.0, 0.0, -99
    while t < len(days):
        line = 100.0 if stage == "rp" else min(peak - 2000.0, 100.0)
        n = sizer(pnl - line)
        eq, bust = pnl, False
        for usd in days[t]:
            eq += usd * n
            if eq <= line:
                bust = True
                break
        t += 1
        if bust:
            cash -= M.EVAL_COST
            t += M.EVAL_DAYS
            stage, pnl, peak = "f1", 0.0, 0.0
            continue
        pnl = eq
        peak = max(peak, pnl)
        if pnl >= 4000.0 and (stage == "f1" or t - last_pay >= 5):
            cash += M.PAYOUT
            last_pay = t
            stage, pnl, peak = "rp", 2000.0, 2000.0
    return cash


def main():
    data = sys.argv[1]
    tr = [t for t in G.build(data, set()) if t[4] in ("VG", "Z", "RS")]
    cal_all = sorted({t[0] for t in tr})
    for lo, hi, lab in (("0", "2022", "2018-21"), ("2022", "9", "2022-25")):
        cal = [d for d in cal_all if lo <= d < hi]
        L = M.day_lists(tr, cal)
        rnd = random.Random(113)
        res = {k: [] for k in SIZERS}
        for _ in range(3000):
            idx = []
            while len(idx) < M.HORIZON:
                s = rnd.randrange(0, len(cal) - M.BLOCK)
                idx.extend(range(s, s + M.BLOCK))
            path = [L[i] for i in idx[:M.HORIZON]]
            for k, f in SIZERS.items():
                res[k].append(run_path(path, f))
        print(f"--- {lab}")
        for line in M.summary(res, "flat 3"):
            print("   " + line)


if __name__ == "__main__":
    main()
