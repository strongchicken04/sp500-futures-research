"""Rebuild the book from corrected inputs and compare candidate configurations.

Several components of the book turned out to have been simulated differently
from how they are traded: the gap reversal skipped its entry bar, Monday/
Friday carried a +40 pt target the live indicator does not have, and ORB and
the VWAP band used an equal-weight average where the indicators use true
VWAP. This assembles the book from whichever corrected tag files exist and
falls back to the originals otherwise, printing which source it used, so
every number is traceable to a specific backtest.
"""
from __future__ import annotations

import csv
import os
import sys

sys.path.insert(0, "scripts")
from prop_sim import Trade, simulate, merge, load_tags, by_day, TIERS  # noqa: E402
from vwap_grid_barrier import parse_grid, to_trades, SL_LVLS, TP_LVLS  # noqa: E402
from s8_stop_sweep import parse as parse_mae, trades_for  # noqa: E402
from ladder_sim import ladder, outcomes, lifecycle  # noqa: E402

SPLIT = "2022-01-01"


def first(sp, *names):
    for n in names:
        p = f"{sp}/{n}"
        if os.path.exists(p) and os.path.getsize(p) > 0:
            return p
    return None


def load_components(sp, use_true_vwap=False, mf_variant="MFE"):
    src = {}
    s1p = first(sp, "S1VW_tags.txt") if use_true_vwap else None
    s1p = s1p or first(sp, "s1_tags.txt")
    vgp = first(sp, "VGVW_tags.txt") if use_true_vwap else None
    vgp = vgp or first(sp, "vg_tags.txt")
    s8p = first(sp, "S8FIX_tags.txt", "s8mae_tags.txt")
    mfp = first(sp, "MFEOD_tags.txt")
    src.update(s1=s1p, vg=vgp, s8=s8p, mf=mfp or "combo_tags.txt (TP40 legacy)")
    s1 = load_tags(s1p, fmt="s1")
    vg = to_trades(parse_grid(vgp), SL_LVLS.index(25.0), TP_LVLS.index(100.0))
    s8 = trades_for(parse_mae(s8p), "pct", 0)
    if mfp:
        mf = [t for t in load_tags(mfp, fmt="combo") if t.strat == mf_variant]
    else:
        mf = [t for t in load_tags(f"{sp}/combo_tags.txt", fmt="combo")
              if t.strat == "MONFRI"]
    wed = {}
    for key, name, kind in (("s1", "WEDS1_tags.txt", "s1"),
                            ("vg", "WEDVG_tags.txt", "vg"),
                            ("s8", "WEDS8_tags.txt", "s8")):
        p = first(sp, name)
        if not p:
            continue
        if kind == "s1":
            wed[key] = load_tags(p, fmt="s1")
        elif kind == "vg":
            wed[key] = to_trades(parse_grid(p), SL_LVLS.index(25.0),
                                 TP_LVLS.index(100.0))
        else:
            wed[key] = trades_for(parse_mae(p), "pct", 0)
        src["wed_" + key] = p
    gcp = first(sp, "XGC_tags.txt")
    gc = load_tags(gcp, fmt="s1") if gcp else []
    src["gc"] = gcp
    return {"s1": s1, "vg": vg, "s8": s8, "mf": mf, "wed": wed, "gc": gc}, src


def rvol():
    reg = {}
    with open("results/nq_panel_real.csv") as fh:
        for r in csv.DictReader(fh):
            try:
                reg[r["date"]] = float(r["rvol20"])
            except (ValueError, KeyError):
                continue
    return reg


def dollars(ts, pp):
    return [Trade(t.date, t.points * pp, t.strat) for t in ts]


def book(c, reg, ceiling=0.30, with_wed=False, mnq=1, gc_micros=0):
    """Dollar-denominated trades for `mnq` MNQ plus optional gold."""
    def g(ts):
        return [t for t in ts if reg.get(t.date, 9.0) < ceiling]
    parts = [c["s1"], c["vg"], c["s8"], c["mf"]]
    if with_wed:
        parts += list(c["wed"].values())
    nq = dollars(merge(*[g(p) for p in parts]), 2.0 * mnq)
    if gc_micros:
        nq = merge(nq, dollars(c["gc"], 10.0 * gc_micros))
    return nq


def stats(ts, ds, lo=None, hi=None):
    TIERS.clear()
    TIERS.append((0.0, 1.0, ds))
    ts = [t for t in ts if (lo is None or t.date >= lo) and (hi is None or t.date < hi)]
    r = simulate(ts, window=250, day_stop_profit=1450.0)
    return r.pass_rate, r.bust_rate, r.median_days


def main():
    sp = sys.argv[1]
    reg = rvol()
    orig = list(TIERS)
    for tv in (False, True):
        c, src = load_components(sp, use_true_vwap=tv)
        print("=" * 90)
        print("sources:", {k: os.path.basename(v) if isinstance(v, str) and "/" in v else v
                           for k, v in src.items()})
        print(f"{'config':<40} {'full p/b/med':>16} {'IS p/b':>12} {'OOS p/b':>12}")
        configs = [
            ("3 MNQ, gate .30", dict(mnq=3), 300.0),
            ("3 MNQ, gate .25", dict(mnq=3, ceiling=0.25), 300.0),
            ("3 MNQ + Wed, gate .30", dict(mnq=3, with_wed=True), 300.0),
            ("2 MNQ, gate .30", dict(mnq=2), 240.0),
            ("2 MNQ + Wed, gate .30", dict(mnq=2, with_wed=True), 240.0),
            ("2 MNQ + 4 MGC", dict(mnq=2, gc_micros=4), 300.0),
            ("gold only, 7 MGC", None, 315.0),
            ("gold only, 10 MGC", None, 450.0),
        ]
        for name, kw, ds in configs:
            if kw is None:
                n = 7 if "7" in name else 10
                ts = dollars(c["gc"], 10.0 * n)
            else:
                ts = book(c, reg, **kw)
            a = stats(ts, ds)
            i = stats(ts, ds, hi=SPLIT)
            o = stats(ts, ds, lo=SPLIT)
            print(f"{name:<40} {a[0]:5.1f}/{a[1]:4.1f}/{a[2]:3d} "
                  f"{i[0]:6.1f}/{i[1]:4.1f} {o[0]:6.1f}/{o[1]:4.1f}")
    TIERS.clear()
    TIERS.extend(orig)


if __name__ == "__main__":
    main()
