"""Joint sweep of sizing x daily-stop x portfolio, scored on calendar-time EV.

Pass rate per attempt is not the whole story. A challenge that busts in week 2
frees the trader to start a fresh attempt, while one that times out at week 8
consumes the entire window. Over a fixed calendar budget the fast-failing
configuration can therefore beat the slow one even at equal pass rate, so the
ranking here is expected passes per 24 weeks rather than raw pass rate.
"""
from __future__ import annotations

import sys

sys.path.insert(0, "scripts")
from prop_sim import (  # noqa: E402
    Trade, simulate, merge, load_tags, TIERS, WINDOW_DAYS,
)
from vwap_grid_barrier import parse_grid, to_trades, SL_LVLS, TP_LVLS  # noqa: E402

CALENDAR_DAYS = 120  # ~24 weeks of attempts


def ev_passes(res, calendar_days: int = CALENDAR_DAYS) -> float:
    """Expected number of passes within a fixed calendar budget.

    A passing attempt ends on its pass day; a busting one ends early and is
    restarted; a timeout burns the whole window.
    """
    if res.n == 0:
        return 0.0
    p = res.passed / res.n
    b = res.busted / res.n
    t = res.timeout / res.n
    mean_pass_days = sum(res.pass_days) / len(res.pass_days) if res.pass_days else WINDOW_DAYS
    # Busts resolve faster than the full window; approximate at half.
    mean_days = p * mean_pass_days + b * (WINDOW_DAYS * 0.45) + t * WINDOW_DAYS
    if mean_days <= 0:
        return 0.0
    return (calendar_days / mean_days) * p


def main() -> None:
    sp = sys.argv[1]
    s1 = load_tags(f"{sp}/s1_tags.txt", fmt="s1")
    combo = load_tags(f"{sp}/combo_tags.txt", fmt="combo")
    monfri = [t for t in combo if t.strat == "MONFRI"]
    rows = parse_grid(f"{sp}/vg_tags.txt")
    vwap = to_trades(rows, SL_LVLS.index(25.0), TP_LVLS.index(100.0))

    ports = {
        "S1+VWAP25/100": merge(s1, vwap),
        "S1+VWAP+MONFRI": merge(s1, vwap, monfri),
        "S1 only": s1,
    }

    sizings = {
        "2/3/NQ (cur)": [(0.0, 4.0, 400.0), (400.0, 6.0, 500.0), (1000.0, 20.0, 600.0)],
        "flat 2 MNQ":   [(0.0, 4.0, 400.0)],
        "flat 3 MNQ":   [(0.0, 6.0, 400.0)],
        "flat 4 MNQ":   [(0.0, 8.0, 400.0)],
        "flat 5 MNQ":   [(0.0, 10.0, 400.0)],
        "3/5 MNQ":      [(0.0, 6.0, 400.0), (800.0, 10.0, 500.0)],
        "3/5/NQ":       [(0.0, 6.0, 400.0), (800.0, 10.0, 500.0), (1600.0, 20.0, 600.0)],
        "2/4/6 MNQ":    [(0.0, 4.0, 400.0), (500.0, 8.0, 500.0), (1200.0, 12.0, 600.0)],
        "4/6 MNQ":      [(0.0, 8.0, 400.0), (900.0, 12.0, 500.0)],
    }

    stop_mults = [0.4, 0.6, 0.8, 1.0, 1.5]

    orig = list(TIERS)
    results = []

    for pname, port in ports.items():
        for sname, sch in sizings.items():
            for mult in stop_mults:
                TIERS.clear()
                TIERS.extend([(f, d, s * mult) for f, d, s in sch])
                r = simulate(port)
                results.append({
                    "port": pname, "size": sname, "mult": mult,
                    "pass": r.pass_rate, "bust": r.bust_rate,
                    "ev": ev_passes(r), "med": r.median_days,
                })

    TIERS.clear()
    TIERS.extend(orig)

    print("=" * 92)
    print("TOP 20 by raw PASS RATE")
    print("=" * 92)
    print(f"{'portfolio':<17} {'sizing':<14} {'stopx':>5} | {'pass':>6} {'bust':>6} "
          f"{'med_d':>6} | {'EV/24wk':>7}")
    for r in sorted(results, key=lambda x: -x["pass"])[:20]:
        print(f"{r['port']:<17} {r['size']:<14} {r['mult']:5.1f} | "
              f"{r['pass']:5.1f}% {r['bust']:5.1f}% {r['med']:6.0f} | {r['ev']:7.2f}")

    print()
    print("=" * 92)
    print("TOP 20 by EXPECTED PASSES per 24 weeks (accounts for fast failure)")
    print("=" * 92)
    print(f"{'portfolio':<17} {'sizing':<14} {'stopx':>5} | {'pass':>6} {'bust':>6} "
          f"{'med_d':>6} | {'EV/24wk':>7}")
    for r in sorted(results, key=lambda x: -x["ev"])[:20]:
        print(f"{r['port']:<17} {r['size']:<14} {r['mult']:5.1f} | "
              f"{r['pass']:5.1f}% {r['bust']:5.1f}% {r['med']:6.0f} | {r['ev']:7.2f}")

    print()
    print("=" * 92)
    print("BEST LOW-BUST configs (bust < 15%) — for a single careful attempt")
    print("=" * 92)
    low = [r for r in results if r["bust"] < 15.0]
    for r in sorted(low, key=lambda x: -x["pass"])[:12]:
        print(f"{r['port']:<17} {r['size']:<14} {r['mult']:5.1f} | "
              f"{r['pass']:5.1f}% {r['bust']:5.1f}% {r['med']:6.0f} | {r['ev']:7.2f}")


if __name__ == "__main__":
    main()
