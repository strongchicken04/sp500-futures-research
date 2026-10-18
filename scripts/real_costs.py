"""Lifecycle with the account's real commissions.

Commissions per micro round trip (from the account): M2K $0.50, MYM $0.50,
MGC $0.80; MNQ assumed the same $0.50. Slippage is still unmeasured, so each
mix runs at 0 and 1 tick per round trip (MNQ/M2K/MYM tick $0.50, MGC $1.00),
and once more with commissions doubled in case the quote is per side.
A unit is 1 MNQ plus the listed micros of the other markets; units are sized
by drawdown room (room // K, max 4).
"""
from __future__ import annotations

import sys

sys.path.insert(0, "scripts")
from prop_sim import Trade, merge, load_tags  # noqa: E402
from rescore_all import load_components, rvol, book  # noqa: E402
from mixed_accounts import calendar_days, sim_groups  # noqa: E402
from final_lifecycle import staged, lad, stage_line  # noqa: E402

COMM = {"MNQ": 0.50, "M2K": 0.50, "MYM": 0.50, "MGC": 0.80}
TICK = {"MNQ": 0.50, "M2K": 0.50, "MYM": 0.50, "MGC": 1.00}
PP = {"M2K": 5.0, "MYM": 0.5, "MGC": 10.0}


def net(ts, pp, n, inst, ticks, mult):
    c = n * (COMM[inst] * mult + ticks * TICK[inst])
    return [Trade(t.date, t.points * pp * n - c, t.strat) for t in ts]


def main():
    sp = sys.argv[1]
    reg = rvol()
    c, _ = load_components(sp)
    nq = book(c, reg, mnq=1)
    gate = lambda ts: [t for t in ts if reg.get(t.date, 9.0) < 0.30]
    other = {"M2K": gate(load_tags(f"{sp}/XRTY_tags.txt", fmt="s1")),
             "MYM": gate(load_tags(f"{sp}/XYM_tags.txt", fmt="s1"))}
    gold = c["gc"] + load_tags(f"{sp}/XGCS_tags.txt", fmt="s1")
    units = [("NQ", {}, (400, 500, 400)),
             ("NQ + 2 MYM", {"MYM": 2}, (700, 800, 700)),
             ("NQ + 2.33 M2K", {"M2K": 2.33}, (500, 600, 500)),
             ("NQ + 2 MYM + 2.33 M2K", {"MYM": 2, "M2K": 2.33}, (800, 900, 800))]
    for mult, ticks in ((1, 0), (1, 1), (2, 1)):
        print(f"\n===== commission x{mult}, slippage {ticks} tick per round trip =====")
        T = {}
        for name, mix, (k1, k2, k3) in units:
            ts = net(nq, 1.0, 1, "MNQ", ticks, mult)
            for inst, n in mix.items():
                ts = merge(ts, net(other[inst], PP[inst], n, inst, ticks, mult))
            d = calendar_days(ts, sorted(set(t.date for t in ts)))
            T[name] = staged(d, lad(k1, 4, 75), lad(k2, 4, 75), lad(k3, 4, 75))
            stage_line(name, T[name])
        g = sorted(net(gold, 10.0, 1, "MGC", ticks, mult), key=lambda t: t.date)
        dg = calendar_days(g, sorted(set(t.date for t in g)))
        T["GC 2-way"] = staged(dg, *(lad(200, 10, 35),) * 3)
        stage_line("GC 2-way (separate account)", T["GC 2-way"])
        for name in T:
            r = sim_groups([(5, T[name])])
            print(f"   5x {name:<24} p10 {r['p10']:9,.0f}  median {r['p50']:9,.0f}  p90 {r['p90']:9,.0f}")
        r = sim_groups([(3, T["NQ + 2 MYM"]), (2, T["GC 2-way"])])
        print(f"   3x NQ+MYM + 2x GC          p10 {r['p10']:9,.0f}  median {r['p50']:9,.0f}  p90 {r['p90']:9,.0f}")


if __name__ == "__main__":
    main()
