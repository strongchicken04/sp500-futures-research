"""Does running the ORB workhorse on other instruments add pass rate?

Same rule, different market. The hope is that ES, RTY, YM or gold trend on
different days from NQ, so a second stream of the proven logic lifts the
book without the variance penalty that sank the new NQ signals.

Everything is converted to dollars, because a point means something
different on every contract. Each instrument is sized in micros so its
average losing trade costs about the same as an NQ ORB loss at the chosen
MNQ count -- otherwise a "gain" would just be extra leverage in disguise.
"""
from __future__ import annotations

import csv
import statistics as st
import sys
from collections import defaultdict

sys.path.insert(0, "scripts")
from prop_sim import Trade, simulate, merge, load_tags, TIERS  # noqa: E402
from vwap_grid_barrier import parse_grid, to_trades, SL_LVLS, TP_LVLS  # noqa: E402
from s8_stop_sweep import parse as parse_mae, trades_for  # noqa: E402

MICRO = {"NQ": 2.0, "ES": 5.0, "RTY": 5.0, "YM": 0.5, "GC": 10.0}
SPLIT = "2022-01-01"


def dollars(trades, per_pt):
    return [Trade(t.date, t.points * per_pt, t.strat) for t in trades]


def daily(trades):
    d = defaultdict(float)
    for t in trades:
        d[t.date] += t.points
    return d


def corr(a, b):
    keys = sorted(set(a) | set(b))
    x = [a.get(k, 0.0) for k in keys]
    y = [b.get(k, 0.0) for k in keys]
    mx, my = st.mean(x), st.mean(y)
    num = sum((p - mx) * (q - my) for p, q in zip(x, y))
    den = (sum((p - mx) ** 2 for p in x) * sum((q - my) ** 2 for q in y)) ** 0.5
    return num / den if den else 0.0


def main() -> None:
    sp = sys.argv[1]
    insts = sys.argv[2:] or ["GC", "RTY", "ES", "YM"]
    reg = {}
    with open("results/nq_panel_real.csv") as fh:
        for r in csv.DictReader(fh):
            try:
                reg[r["date"]] = float(r["rvol20"])
            except (ValueError, KeyError):
                continue

    def gate(ts):
        return [t for t in ts if reg.get(t.date, 9.0) < 0.30]

    n_mnq = 3
    nq_pp = MICRO["NQ"] * n_mnq
    s1 = load_tags(f"{sp}/s1_tags.txt", fmt="s1")
    g = parse_grid(f"{sp}/vg_tags.txt")
    vwap = to_trades(g, SL_LVLS.index(25.0), TP_LVLS.index(100.0))
    monfri = [t for t in load_tags(f"{sp}/combo_tags.txt", fmt="combo")
              if t.strat == "MONFRI"]
    s8 = trades_for(parse_mae(f"{sp}/s8mae_tags.txt"), "pct", 0)
    book = dollars(merge(gate(s1), gate(vwap), gate(monfri), gate(s8)), nq_pp)
    s1_loss = st.mean([t.points for t in s1 if t.points <= 0]) * nq_pp

    orig = list(TIERS)
    TIERS.clear()
    TIERS.append((0.0, 1.0, 300.0))  # trades already in dollars

    def sc(ts, part=None):
        if part == "IS":
            ts = [t for t in ts if t.date < SPLIT]
        elif part == "OOS":
            ts = [t for t in ts if t.date >= SPLIT]
        r = simulate(ts, window=250, day_stop_profit=1450.0)
        return r.pass_rate, r.bust_rate, r.median_days

    b = sc(book), sc(book, "IS"), sc(book, "OOS")
    print(f"NQ book at {n_mnq} MNQ, \$-denominated, 250d: full "
          f"{b[0][0]:.1f}/{b[0][1]:.1f}/{b[0][2]:.0f}  IS {b[1][0]:.1f}/{b[1][1]:.1f}"
          f"  OOS {b[2][0]:.1f}/{b[2][1]:.1f}")
    print(f"NQ ORB average loss at {n_mnq} MNQ: \${s1_loss:.0f}\n")

    for inst in insts:
        path = f"{sp}/X{inst}_tags.txt"
        try:
            x = load_tags(path, fmt="s1")
        except FileNotFoundError:
            print(f"{inst}: no tags yet")
            continue
        if len(x) < 100:
            print(f"{inst}: only {len(x)} trades")
            continue
        v = [t.points for t in x]
        loss = st.mean([p for p in v if p <= 0])
        # micros needed to match the NQ ORB's average dollar loss
        n_parity = max(1, round(s1_loss / (loss * MICRO[inst])))
        yrs = [t for t in x]
        print(f"=== {inst}  n={len(v)}  WR {sum(1 for p in v if p > 0)/len(v)*100:.1f}%"
              f"  avg {st.mean(v):+.3f} pt  avgL {loss:+.3f} pt  "
              f"IS avg {st.mean([t.points for t in yrs if t.date < SPLIT]):+.3f}"
              f"  OOS avg {st.mean([t.points for t in yrs if t.date >= SPLIT]):+.3f}")
        print(f"    risk-parity size: {n_parity} micro(s)")
        for mult in (0.5, 1.0):
            n = max(1, round(n_parity * mult))
            xd = gate(dollars(x, MICRO[inst] * n))
            c = corr(daily(book), daily(xd))
            al = sc(xd)
            f = sc(merge(book, xd)), sc(merge(book, xd), "IS"), sc(merge(book, xd), "OOS")
            print(f"    {n:2d} micro  corr w/ book {c:+.2f}  alone {al[0]:5.1f}/"
                  f"{al[1]:4.1f}   +book {f[0][0]:5.1f}/{f[0][1]:4.1f}/{f[0][2]:3.0f} "
                  f"({f[0][0]-b[0][0]:+5.1f})  IS {f[1][0]:5.1f} ({f[1][0]-b[1][0]:+5.1f})"
                  f"  OOS {f[2][0]:5.1f} ({f[2][0]-b[2][0]:+5.1f})")
        print()
    TIERS.clear()
    TIERS.extend(orig)


if __name__ == "__main__":
    main()
