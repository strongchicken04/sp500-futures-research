"""Five accounts: all on NQ, or split between NQ and gold?

Copytrading one strategy across five accounts makes them a single bet at
five times the size -- they pass and bust together. Gold ORB returns have a
daily correlation of about +0.06 with the NQ book, so accounts running gold
should fail on different days. This simulates groups of accounts on one
shared calendar, so whatever correlation exists in the data is preserved,
through the full lifecycle: evaluation, first funded cycle, repeat payouts.
"""
from __future__ import annotations

import random
import statistics as st
import sys

sys.path.insert(0, "scripts")
from prop_sim import by_day  # noqa: E402
from ladder_sim import outcomes  # noqa: E402
from rescore_all import load_components, rvol, book, dollars  # noqa: E402


def calendar_days(trades, cal):
    d = by_day(trades)
    return [(k, d.get(k, [])) for k in cal]


def tables(days, sizer):
    return {
        "ev": outcomes(days, sizer, start_pnl=0.0, target=3000.0, consistency=True),
        "f1": outcomes(days, sizer, start_pnl=0.0, target=4000.0, consistency=False),
        "rp": outcomes(days, sizer, start_pnl=2000.0, target=4000.0,
                       consistency=False, locked=100.0),
    }


def sim_groups(groups, horizon=504, trials=20000, fee=150.0, payout=1800.0, seed=7):
    """groups: list of (n_accounts, tables). Shared start date per trial."""
    rnd = random.Random(seed)
    M = min(len(tb["ev"]) for _, tb in groups)
    totals, zero_payout = [], 0
    for _ in range(trials):
        t0 = rnd.randrange(0, M)
        cash = 0.0
        paid_any = False
        for n, tb in groups:
            t = 0
            stage = "ev"
            while t < horizon:
                i = (t0 + t) % M
                if stage == "ev":
                    o, d = tb["ev"][i]
                    t += d
                    cash -= n * fee
                    if o == "pass":
                        stage = "f1"
                    elif o == "timeout":
                        t += 5
                elif stage == "f1":
                    o, d = tb["f1"][i]
                    t += d
                    if o == "pass":
                        cash += n * payout
                        paid_any = True
                        stage = "rp"
                    elif o == "bust":
                        stage = "ev"
                else:
                    o, d = tb["rp"][i]
                    t += max(d, 5)
                    if o == "pass":
                        cash += n * payout
                        paid_any = True
                    elif o == "bust":
                        stage = "ev"
        totals.append(cash)
        zero_payout += not paid_any
    totals.sort()
    q = lambda p: totals[int(len(totals) * p)]
    return {"p10": q(0.10), "p25": q(0.25), "p50": q(0.50), "p90": q(0.90),
            "sd": st.pstdev(totals), "none": zero_payout / trials * 100}


def main():
    sp = sys.argv[1]
    reg = rvol()
    c, _ = load_components(sp)
    nq = book(c, reg, mnq=1)              # dollars per 1 MNQ
    gc = dollars(c["gc"], 10.0)           # dollars per 1 MGC
    cal = sorted(set(t.date for t in nq) | set(t.date for t in gc))
    nq_days = calendar_days(nq, cal)
    gc_days = calendar_days(gc, cal)

    def flat(n, ds):
        return lambda room: (float(n), ds)

    def lad(K, cap, unit_ds):
        def f(room):
            n = max(1, min(cap, int(room // K)))
            return float(n), unit_ds * n + 75.0
        return f

    tab = {
        "NQ 3 flat": tables(nq_days, flat(3, 300.0)),
        "NQ ladder K300c4": tables(nq_days, lad(300, 4, 75.0)),
        "GC 7 flat": tables(gc_days, flat(7, 315.0)),
        "GC ladder K200c10": tables(gc_days, lad(200, 10, 35.0)),
    }
    for k, tb in tab.items():
        for stg in ("ev", "f1", "rp"):
            o = tb[stg]
            p = sum(1 for x, _ in o if x == "pass") / len(o) * 100
            b = sum(1 for x, _ in o if x == "bust") / len(o) * 100
            md = sorted(d for x, d in o if x == "pass")
            print(f"{k:<20} {stg}: pass {p:5.1f}%  bust {b:5.1f}%  "
                  f"median {md[len(md)//2] if md else 0} d")
    print()
    mixes = [
        ("5 NQ (3 flat)", [(5, tab["NQ 3 flat"])]),
        ("5 NQ (ladder)", [(5, tab["NQ ladder K300c4"])]),
        ("5 GC (7 flat)", [(5, tab["GC 7 flat"])]),
        ("5 GC (ladder)", [(5, tab["GC ladder K200c10"])]),
        ("3 NQ ladder + 2 GC ladder", [(3, tab["NQ ladder K300c4"]), (2, tab["GC ladder K200c10"])]),
        ("2 NQ ladder + 3 GC ladder", [(2, tab["NQ ladder K300c4"]), (3, tab["GC ladder K200c10"])]),
        ("3 NQ flat + 2 GC flat", [(3, tab["NQ 3 flat"]), (2, tab["GC 7 flat"])]),
    ]
    print(f"{'five accounts':<28} {'p10':>9} {'p25':>9} {'median':>9} {'p90':>9} {'sd':>8} {'no payout':>10}")
    for name, groups in mixes:
        r = sim_groups(groups)
        print(f"{name:<28} {r['p10']:9,.0f} {r['p25']:9,.0f} {r['p50']:9,.0f} "
              f"{r['p90']:9,.0f} {r['sd']:8,.0f} {r['none']:9.1f}%")


if __name__ == "__main__":
    main()
