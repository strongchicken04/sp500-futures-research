"""Re-run the lifecycle with trading costs, which every earlier score left out.

Each Trade is one round trip. Cost per micro contract per round trip =
commission (both sides) + slippage in ticks. MNQ and M2K ticks are worth
$0.50, MGC $1.00. Three scenarios: commission only, + one tick, + two ticks.
Russell and gold earn only a few dollars per micro per trade, so they are the
streams most exposed.
"""
from __future__ import annotations

import sys

sys.path.insert(0, "scripts")
from prop_sim import Trade, merge, load_tags  # noqa: E402
from rescore_all import load_components, rvol, book  # noqa: E402
from mixed_accounts import calendar_days, sim_groups  # noqa: E402
from final_lifecycle import staged, flat, lad, stage_line  # noqa: E402

COMM = 1.0                    # $ per micro, round trip
TICK = {"MNQ": 0.5, "M2K": 0.5, "MGC": 1.0}


def net(ts, pp, n_micro, inst, ticks):
    c = n_micro * (COMM + ticks * TICK[inst])
    return [Trade(t.date, t.points * pp * n_micro - c, t.strat) for t in ts]


def main():
    sp = sys.argv[1]
    reg = rvol()
    c, _ = load_components(sp)
    nq = book(c, reg, mnq=1)
    rty = [t for t in load_tags(f"{sp}/XRTY_tags.txt", fmt="s1")
           if reg.get(t.date, 9.0) < 0.30]
    gs = load_tags(f"{sp}/XGCS_tags.txt", fmt="s1")
    for ticks in (0, 1, 2):
        print(f"\n===== cost: ${COMM:.2f} commission + {ticks} tick(s) slippage per micro =====")
        q = net(nq, 1.0, 1, "MNQ", ticks)
        nr = merge(q, net(rty, 5.0, 2.33, "M2K", ticks))
        g2 = merge(net(c["gc"], 10.0, 1, "MGC", ticks), net(gs, 10.0, 1, "MGC", ticks))
        cal = sorted(set(t.date for t in nr) | set(t.date for t in g2))
        dq, dnr, dg = (calendar_days(x, cal) for x in (q, nr, g2))
        T = {
            "NQ 3/2/3": staged(dq, flat(3, 75), flat(2, 75), flat(3, 75)),
            "NQ+RTY 3/2/3": staged(dnr, flat(3, 75), flat(2, 75), flat(3, 75)),
            "GC 2-way flat 7": staged(dg, *(flat(7, 35),) * 3),
            "GC 2-way lad K200c10": staged(dg, *(lad(200, 10, 35),) * 3),
        }
        for k, tb in T.items():
            stage_line(k, tb)
        mixes = [("5 NQ", [(5, T["NQ 3/2/3"])]),
                 ("5 NQ+RTY", [(5, T["NQ+RTY 3/2/3"])]),
                 ("3 NQ + 2 GC lad", [(3, T["NQ 3/2/3"]), (2, T["GC 2-way lad K200c10"])]),
                 ("3 NQ+RTY + 2 GC lad", [(3, T["NQ+RTY 3/2/3"]), (2, T["GC 2-way lad K200c10"])]),
                 ("5 GC lad", [(5, T["GC 2-way lad K200c10"])])]
        for name, groups in mixes:
            r = sim_groups(groups)
            print(f"   {name:<26} p10 {r['p10']:9,.0f}  median {r['p50']:9,.0f}  p90 {r['p90']:9,.0f}")


if __name__ == "__main__":
    main()
