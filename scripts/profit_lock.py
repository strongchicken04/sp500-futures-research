"""Daily profit lock for the funded book (day shift 2026-10-23): after the
realised day P&L reaches +X, no new entries that day (open trades run to their
normal exits). X in {none, $400, $800, $1,200}, fixed in advance. Time-aware
sim at flat 3 MNQ per leg, ORB+VG+Z+RS; also the share of funded accounts that
reach the first payout.
Usage: profit_lock.py DATA_DIR
"""
from __future__ import annotations

import sys
from collections import defaultdict

sys.path.insert(0, "scripts")
from prop_sim import Trade  # noqa: E402
from timed_book import legs, outcomes, life  # noqa: E402


def days_lock(trades, cal, n, lock, use):
    by = defaultdict(list)
    for t in trades:
        if t[4] in use:
            by[t[0]].append(t)
    out = []
    for d in cal:
        taken = []
        for t in sorted(by.get(d, []), key=lambda t: t[1]):
            realised = sum(x[3] * n for x in taken if x[2] <= t[1])
            if realised >= lock:
                continue
            taken.append(t)
        out.append((d, [Trade(d, t[3], t[4]) for t in sorted(taken, key=lambda t: t[2])]))
    return out


def main():
    data = sys.argv[1]
    tr = legs(f"{data}/fixed", data)
    cal = sorted({t[0] for t in tr})
    use = ("ORB", "VG", "Z", "RS")
    print("flat 3, ORB+VG+Z+RS; mean 24-month cash per account | share of funded accounts reaching the first payout")
    for lock in (10 ** 9, 400, 800, 1200):
        res, hit = [], []
        for lo, hi in (("0", "2022"), ("2022", "9")):
            c = [d for d in cal if lo <= d < hi]
            dd = days_lock(tr, c, 3, lock, use)
            sz = lambda room: (3.0, 10 ** 9)
            f1 = outcomes(dd, sz, window=300, start_pnl=0.0, target=4000.0, consistency=False)
            rp = outcomes(dd, sz, window=300, start_pnl=2000.0, target=4000.0, consistency=False, locked=100.0)
            res.append(life(f1, rp))
            hit.append(sum(1 for r, _ in f1 if r == "pass") / max(1, len(f1)))
        lab = "none" if lock > 10 ** 6 else f"+${lock}"
        print(f"   lock {lab:>6}   ${res[0]:8,.0f} | ${res[1]:8,.0f}    first payout {hit[0] * 100:.0f}% | {hit[1] * 100:.0f}%")


if __name__ == "__main__":
    main()
