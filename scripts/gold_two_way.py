"""Gold ORB long + short mirror as a separate account, against NQ + Russell.

The short mirror (break below the OR low and VWAP) is positive in every year
2018-2025 despite gold rising, so the long ORB is not just drift. This checks
whether trading both legs makes a gold account worth one of the five slots.
"""
from __future__ import annotations

import sys

sys.path.insert(0, "scripts")
from prop_sim import merge, load_tags  # noqa: E402
from rescore_all import load_components, rvol, book, dollars  # noqa: E402
from mixed_accounts import calendar_days, sim_groups  # noqa: E402
from final_lifecycle import staged, flat, lad, stage_line  # noqa: E402


def main():
    sp = sys.argv[1]
    reg = rvol()
    c, _ = load_components(sp)
    nq = book(c, reg, mnq=1)
    rty = [t for t in load_tags(f"{sp}/XRTY_tags.txt", fmt="s1")
           if reg.get(t.date, 9.0) < 0.30]
    unit_nr = merge(nq, dollars(rty, 5.0 * 2.33))
    gl = dollars(c["gc"], 10.0)
    gs = dollars(load_tags(f"{sp}/XGCS_tags.txt", fmt="s1"), 10.0)
    g2 = merge(gl, gs)
    cal = sorted(set(t.date for t in unit_nr) | set(t.date for t in g2))
    d_nr, d_gl, d_g2 = (calendar_days(x, cal) for x in (unit_nr, gl, g2))

    T = {
        "NQ+RTY 3/2/3": staged(d_nr, flat(3, 75), flat(2, 75), flat(3, 75)),
        "GC long lad K200c10": staged(d_gl, *(lad(200, 10, 35),) * 3),
        "GC long+short flat 5": staged(d_g2, *(flat(5, 35),) * 3),
        "GC long+short flat 7": staged(d_g2, *(flat(7, 35),) * 3),
        "GC long+short lad K250c8": staged(d_g2, *(lad(250, 8, 35),) * 3),
        "GC long+short lad K200c10": staged(d_g2, *(lad(200, 10, 35),) * 3),
    }
    print("per-stage pass/bust/median trading days")
    for k, tb in T.items():
        stage_line(k, tb)

    nr = T["NQ+RTY 3/2/3"]
    mixes = [("5 NQ+RTY", [(5, nr)])]
    for g in list(T)[1:]:
        mixes.append((f"5 {g}", [(5, T[g])]))
        mixes.append((f"4 NQ+RTY + 1 {g}", [(4, nr), (1, T[g])]))
        mixes.append((f"3 NQ+RTY + 2 {g}", [(3, nr), (2, T[g])]))
    print(f"\n{'five accounts, 24 months':<44} {'p10':>9} {'median':>9} {'p90':>9}")
    for name, groups in mixes:
        r = sim_groups(groups)
        print(f"{name:<44} {r['p10']:9,.0f} {r['p50']:9,.0f} {r['p90']:9,.0f}")


if __name__ == "__main__":
    main()
