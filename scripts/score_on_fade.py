"""Score the preregistered overnight-level fade on prop-account pass rate.

The strategy fades the first RTH touch of the overnight high (short), low
(long) and midpoint (toward the RTH open) with a fixed 1:1 bracket, and only
on days whose overnight range is at least 65 points. Its per-trade evidence is
the strongest in the repo (z = +12.7) but it was only ever scored on
expectancy.

Codes per bracket: T target first, S stop first, B both in one bar (scored as
a stop), E neither by the close (scored at the RTH close), N never touched.
A 0.75-point round-trip cost is charged on every trade, as in the
preregistration.

Caveat carried into every number here: entries assume a resting limit filled
exactly at the level on first touch. An exact touch that reverses is the case
most likely to go unfilled live and also the case most likely to win, so these
figures are an upper bound until re-exported with trade-through fills.
"""
from __future__ import annotations

import csv
import json
import statistics as st
import sys

sys.path.insert(0, "scripts")
from prop_sim import Trade, simulate, merge, TIERS  # noqa: E402
from score_multi import load_book  # noqa: E402

COST = 0.75
SPLIT = "2022-01-01"


def trades(rows, bracket="15.0", min_range=65.0, legs=("H", "L", "M"),
           cost=COST):
    out = []
    B = float(bracket)
    for r in rows:
        if r["onh"] - r["onl"] < min_range:
            continue
        for leg in legs:
            if not r["t" + leg]:
                continue
            res = r["res" + leg][bracket]
            if res == "N":
                continue
            if leg == "H":
                d = -1
            elif leg == "L":
                d = 1
            else:
                d = r["dM"]
                if d == 0:
                    continue
            if res == "T":
                p = B
            elif res in ("S", "B"):
                p = -B
            else:
                p = d * (r["close"] - r["e" + leg])
            out.append(Trade(r["date"], p - cost, "ONF" + leg))
    return out


def main() -> None:
    sp = sys.argv[1]
    rows = json.load(open("results/vix_band/on_fade_firsthit.json"))
    reg = {}
    with open("results/nq_panel_real.csv") as fh:
        for r in csv.DictReader(fh):
            try:
                reg[r["date"]] = float(r["rvol20"])
            except (ValueError, KeyError):
                continue

    def gate(ts):
        return [t for t in ts if reg.get(t.date, 9.0) < 0.30]

    book = load_book(sp, gate)
    orig = list(TIERS)

    def sc(ts, w=120):
        r = simulate(ts, window=w, day_stop_profit=1450.0)
        return r.pass_rate, r.bust_rate

    for size_name, tier in (("3 MNQ", (0.0, 6.0, 300.0)),
                            ("2 MNQ", (0.0, 4.0, 240.0))):
        TIERS.clear()
        TIERS.append(tier)
        print(f"===== {size_name}, 120-day window, vol-gated =====")
        b = sc(book)
        bi = sc([t for t in book if t.date < SPLIT])
        bo = sc([t for t in book if t.date >= SPLIT])
        print(f"book alone: full {b[0]:.1f}/{b[1]:.1f}  IS {bi[0]:.1f}/{bi[1]:.1f}"
              f"  OOS {bo[0]:.1f}/{bo[1]:.1f}")
        for legs in (("H", "L", "M"), ("L",), ("M",), ("H",), ("L", "M")):
            for br in ("10.0", "15.0", "20.0"):
                tr = gate(trades(rows, br, legs=legs))
                v = [t.points for t in tr]
                al = sc(tr)
                f = sc(merge(book, tr))
                o = sc(merge([t for t in book if t.date >= SPLIT],
                             [t for t in tr if t.date >= SPLIT]))
                print(f"  legs {''.join(legs):<3} B={br[:-2]:>2}  n={len(v):4d} "
                      f"avg {st.mean(v):+5.2f}  alone {al[0]:5.1f}/{al[1]:4.1f}  "
                      f"+book {f[0]:5.1f}/{f[1]:4.1f} ({f[0]-b[0]:+5.1f})  "
                      f"OOS {o[0]:5.1f}/{o[1]:4.1f} ({o[0]-bo[0]:+5.1f})")
        print()
    TIERS.clear()
    TIERS.extend(orig)


if __name__ == "__main__":
    main()
