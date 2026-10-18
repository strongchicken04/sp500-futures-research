"""Final 24-month, five-account comparison on the corrected book.

The book is ORB + VWAP band computed with true VWAP, as traded live; the gap
reversal and Monday/Friday are gone. Compares the current plan (flat 3 MNQ
evaluation, 2 MNQ first funded cycle, 3 MNQ repeats) with a drawdown ladder,
with Russell ORB added to the NQ accounts, and with some accounts switched
to gold ORB. Every group of accounts runs on one shared calendar so the real
cross-market correlation is kept.
"""
from __future__ import annotations

import sys

sys.path.insert(0, "scripts")
from prop_sim import Trade, merge, load_tags  # noqa: E402
from rescore_all import load_components, rvol, book, dollars  # noqa: E402
from mixed_accounts import calendar_days, sim_groups  # noqa: E402
from ladder_sim import outcomes  # noqa: E402


def staged(days, ev, f1, rp):
    return {
        "ev": outcomes(days, ev, start_pnl=0.0, target=3000.0, consistency=True),
        "f1": outcomes(days, f1, start_pnl=0.0, target=4000.0, consistency=False),
        "rp": outcomes(days, rp, start_pnl=2000.0, target=4000.0,
                       consistency=False, locked=100.0),
    }


def flat(n, per_unit_stop, base=75.0):
    return lambda room: (float(n), base + per_unit_stop * n)


def lad(K, cap, per_unit_stop, base=75.0):
    def f(room):
        n = max(1, min(cap, int(room // K)))
        return float(n), base + per_unit_stop * n
    return f


def stage_line(name, tb):
    out = []
    for s in ("ev", "f1", "rp"):
        o = tb[s]
        p = sum(1 for x, _ in o if x == "pass") / len(o) * 100
        b = sum(1 for x, _ in o if x == "bust") / len(o) * 100
        md = sorted(d for x, d in o if x == "pass")
        out.append(f"{s} {p:5.1f}/{b:4.1f}/{md[len(md)//2] if md else 0:3d}")
    print(f"  {name:<34} " + "   ".join(out))


def main():
    sp = sys.argv[1]
    reg = rvol()
    c, _ = load_components(sp)
    nq = book(c, reg, mnq=1)                         # $ per 1 MNQ
    rty = [t for t in load_tags(f"{sp}/XRTY_tags.txt", fmt="s1")
           if reg.get(t.date, 9.0) < 0.30]
    unit_nr = merge(nq, dollars(rty, 5.0 * 2.33))    # 1 MNQ + ~2.33 M2K
    gc = dollars(c["gc"], 10.0)                      # $ per 1 MGC
    cal = sorted(set(t.date for t in nq) | set(t.date for t in gc)
                 | set(t.date for t in rty))
    d_nq = calendar_days(nq, cal)
    d_nr = calendar_days(unit_nr, cal)
    d_gc = calendar_days(gc, cal)

    T = {}
    T["NQ plan 3/2/3"] = staged(d_nq, flat(3, 75), flat(2, 75), flat(3, 75))
    T["NQ ladder K300c4"] = staged(d_nq, *(lad(300, 4, 75),) * 3)
    T["NQ ladder K400c4"] = staged(d_nq, *(lad(400, 4, 75),) * 3)
    T["NQ+RTY flat 3u/2u/3u"] = staged(d_nr, flat(3, 75), flat(2, 75), flat(3, 75))
    T["NQ+RTY ladder K500c4"] = staged(d_nr, *(lad(500, 4, 75),) * 3)
    T["NQ+RTY ladder K600c4"] = staged(d_nr, *(lad(600, 4, 75),) * 3)
    T["GC flat 7"] = staged(d_gc, *(flat(7, 35),) * 3)
    T["GC ladder K200c10"] = staged(d_gc, *(lad(200, 10, 35),) * 3)

    print("per-stage pass/bust/median trading days")
    for k, tb in T.items():
        stage_line(k, tb)

    mixes = [
        ("5 NQ, current plan", [(5, T["NQ plan 3/2/3"])]),
        ("5 NQ, ladder K300", [(5, T["NQ ladder K300c4"])]),
        ("5 NQ, ladder K400", [(5, T["NQ ladder K400c4"])]),
        ("5 NQ+RTY, flat", [(5, T["NQ+RTY flat 3u/2u/3u"])]),
        ("5 NQ+RTY, ladder K500", [(5, T["NQ+RTY ladder K500c4"])]),
        ("5 NQ+RTY, ladder K600", [(5, T["NQ+RTY ladder K600c4"])]),
        ("5 GC, ladder", [(5, T["GC ladder K200c10"])]),
        ("3 NQ+RTY lad + 2 GC lad", [(3, T["NQ+RTY ladder K500c4"]), (2, T["GC ladder K200c10"])]),
        ("2 NQ+RTY lad + 3 GC lad", [(2, T["NQ+RTY ladder K500c4"]), (3, T["GC ladder K200c10"])]),
        ("3 NQ lad K300 + 2 GC lad", [(3, T["NQ ladder K300c4"]), (2, T["GC ladder K200c10"])]),
    ]
    print(f"\n{'five accounts, 24 months':<28} {'p10':>9} {'p25':>9} {'median':>9} {'p90':>9}")
    for name, groups in mixes:
        r = sim_groups(groups)
        print(f"{name:<28} {r['p10']:9,.0f} {r['p25']:9,.0f} {r['p50']:9,.0f} {r['p90']:9,.0f}")


if __name__ == "__main__":
    main()
