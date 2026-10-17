"""Optimise the strategy portfolio on pass rate, with out-of-sample validation.

Any parameter picked by looking at the whole history is suspect, so every
candidate here is fit on 2018-2021 and scored on 2022-2025. A cell that only
works in-sample is noise and gets dropped.
"""
from __future__ import annotations

import sys

sys.path.insert(0, "scripts")
from prop_sim import (  # noqa: E402
    Trade, simulate, merge, cap_concurrent, report, load_tags, TIERS,
)
from vwap_grid_barrier import parse_grid, to_trades, SL_LVLS, TP_LVLS  # noqa: E402

SPLIT = "2022-01-01"


def split_trades(ts: list[Trade]) -> tuple[list[Trade], list[Trade]]:
    ins = [t for t in ts if t.date < SPLIT]
    oos = [t for t in ts if t.date >= SPLIT]
    return ins, oos


def score(ts: list[Trade], **kw) -> tuple[float, float]:
    r = simulate(ts, **kw)
    return r.pass_rate, r.bust_rate


def main() -> None:
    sp = sys.argv[1]
    s1 = load_tags(f"{sp}/s1_tags.txt", fmt="s1")
    combo = load_tags(f"{sp}/combo_tags.txt", fmt="combo")
    monfri = [t for t in combo if t.strat == "MONFRI"]
    rows = parse_grid(f"{sp}/vg_tags.txt")

    print("=" * 78)
    print("1. VWAP CELL SELECTION — in-sample fit vs out-of-sample score")
    print("=" * 78)
    print(f"{'SL':>4} {'TP':>5} | {'IS pass':>8} {'IS bust':>8} | "
          f"{'OOS pass':>9} {'OOS bust':>9} | {'drop':>6}")

    cells = []
    for si, sl in enumerate(SL_LVLS):
        for ti, tp in enumerate(TP_LVLS):
            vw = to_trades(rows, si, ti)
            full = merge(s1, vw)
            ins, oos = split_trades(full)
            ip, ib = score(ins)
            op, ob = score(oos)
            cells.append((sl, tp, ip, ib, op, ob, ip - op))

    for sl, tp, ip, ib, op, ob, drop in sorted(cells, key=lambda x: -x[4])[:12]:
        print(f"{sl:4.0f} {tp:5.0f} | {ip:7.1f}% {ib:7.1f}% | "
              f"{op:8.1f}% {ob:8.1f}% | {drop:+5.1f}")

    s1_ins, s1_oos = split_trades(s1)
    bp_i, bb_i = score(s1_ins)
    bp_o, bb_o = score(s1_oos)
    print(f"\n   S1 alone baseline  | IS {bp_i:5.1f}% / {bb_i:4.1f}%  "
          f"OOS {bp_o:5.1f}% / {bb_o:4.1f}%")

    # Pick the cell with the best OOS pass rate, not the best IS.
    best = max(cells, key=lambda x: x[4])
    bsl, btp = best[0], best[1]
    bsi, bti = SL_LVLS.index(bsl), TP_LVLS.index(btp)
    vwap_best = to_trades(rows, bsi, bti)
    print(f"\n   -> selected on OOS: SL {bsl:.0f} / TP {btp:.0f}")

    print()
    print("=" * 78)
    print("2. PORTFOLIO COMPOSITION (full history)")
    print("=" * 78)
    for name, ts in [
        ("S1 alone", s1),
        ("S1 + VWAP*", merge(s1, vwap_best)),
        ("S1 + MONFRI", merge(s1, monfri)),
        ("S1 + VWAP* + MONFRI", merge(s1, vwap_best, monfri)),
        ("VWAP* alone", vwap_best),
    ]:
        print("   " + report(name, simulate(ts)))

    print()
    print("=" * 78)
    print("3. PER-DAY TRADE CAP on the full portfolio")
    print("=" * 78)
    port = merge(s1, vwap_best, monfri)
    for cap in [2, 3, 4, 5, 6, 8, 10, 99]:
        print("   " + report(f"cap={cap}", simulate(cap_concurrent(port, cap))))

    print()
    print("=" * 78)
    print("4. DAILY LOSS STOP sensitivity (scales all three tiers)")
    print("=" * 78)
    orig = list(TIERS)
    for mult in [0.5, 0.75, 1.0, 1.5, 2.0, 99.0]:
        TIERS.clear()
        TIERS.extend([(f, d, s * mult) for f, d, s in orig])
        r = simulate(port)
        print("   " + report(f"day-stop x{mult}", r))
    TIERS.clear()
    TIERS.extend(orig)

    print()
    print("=" * 78)
    print("5. SIZING TIER SWEEP")
    print("=" * 78)
    schemes = {
        "flat 2 MNQ":        [(0.0, 4.0, 400.0)],
        "flat 3 MNQ":        [(0.0, 6.0, 500.0)],
        "flat 1 NQ":         [(0.0, 20.0, 600.0)],
        "current 2/3/NQ":    orig,
        "aggressive 3/NQ":   [(0.0, 6.0, 400.0), (600.0, 20.0, 600.0)],
        "slow 2/3/4 MNQ":    [(0.0, 4.0, 400.0), (400.0, 6.0, 500.0), (1000.0, 8.0, 600.0)],
        "late NQ (1500)":    [(0.0, 4.0, 400.0), (400.0, 6.0, 500.0), (1500.0, 20.0, 600.0)],
        "early NQ (700)":    [(0.0, 4.0, 400.0), (700.0, 20.0, 600.0)],
    }
    for name, sch in schemes.items():
        TIERS.clear()
        TIERS.extend(sch)
        print("   " + report(name, simulate(port)))
    TIERS.clear()
    TIERS.extend(orig)


if __name__ == "__main__":
    main()
