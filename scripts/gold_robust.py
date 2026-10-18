"""Robustness of the gold ORB: does it survive parameter and direction changes?

An edge that only exists at one opening-range length and one trailing EMA
is a fitted artefact. An edge that only exists long, on an instrument that
more than tripled over the sample, is mostly drift. This compares every
available variant per year and on evaluation pass rate.
"""
import os
import statistics as st
import sys
from collections import defaultdict

sys.path.insert(0, "scripts")
from prop_sim import Trade, simulate, load_tags, TIERS  # noqa: E402

VARIANTS = [("base: OR15, EMA20, long", "XGC"), ("OR30", "XGC30"),
            ("EMA10 trail", "XGCE10"), ("EMA30 trail", "XGCE30"),
            ("SHORT mirror", "XGCS")]


def main():
    sp = sys.argv[1]
    years = [str(y) for y in range(2018, 2026)]
    print(f"{'variant':<24} {'n':>5} {'avg':>7} " + " ".join(y[2:].rjust(6) for y in years)
          + "   eval 7 MGC p/b/med")
    for name, key in VARIANTS:
        path = f"{sp}/{key}_tags.txt"
        if not os.path.exists(path):
            print(f"{name:<24} (pending)")
            continue
        ts = load_tags(path, fmt="s1")
        by = defaultdict(list)
        for t in ts:
            by[t.date[:4]].append(t.points)
        cells = " ".join((f"{st.mean(by[y]):+6.2f}" if by[y] else "    --") for y in years)
        TIERS.clear()
        TIERS.append((0.0, 70.0, 315.0))
        r = simulate(ts, window=250, day_stop_profit=1450.0)
        print(f"{name:<24} {len(ts):5d} {st.mean([t.points for t in ts]):+7.3f} {cells}"
              f"   {r.pass_rate:5.1f}/{r.bust_rate:4.1f}/{r.median_days:3d}")


if __name__ == "__main__":
    main()
