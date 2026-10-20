"""Stack the few robust same-day signals into one trade-a-day sprint.

Each rule below showed a positive grid-smoothed edge on 2018-2021 and stayed
positive on 2022-2025 (score_plateau.py). Note the list was read off both
halves, so its 2022-2025 numbers are no longer a clean out-of-sample test.
On each day only the first signal to fire is taken, with one common bracket.
"""
from __future__ import annotations

import statistics as st
import sys
from collections import defaultdict

sys.path.insert(0, "scripts")
from prop_sim import Trade, merge, load_tags  # noqa: E402
from rescore_all import rvol, load_components, book  # noqa: E402
from mixed_accounts import calendar_days, sim_groups  # noqa: E402
from final_lifecycle import flat, lad, staged, stage_line  # noqa: E402
from ladder_sim import outcomes  # noqa: E402
from score_cond_bracket import parse, add_daily, FILTERS, LEVELS, SPLIT  # noqa: E402

RULES = [  # (type, filter, side)
    ("ONL", "gap up >=0.25%", 1), ("MDU", "after down day", 1), ("IHT", "gap up >=0.25%", 1),
    ("IBU", "gap up >=0.25%", 1), ("NZU", "gap up >=0.25%", 1), ("ORS", "gap up >=0.25%", -1),
    ("CLD", "gap up >=0.25%", -1), ("T1000", "below VWAP", -1),
]


def res(r, side, tp, sl, w):
    ti, si = LEVELS.index(tp), LEVELS.index(sl)
    fav, adv = (r["up"], r["dn"]) if side == 1 else (r["dn"], r["up"])
    t, s = fav[ti], adv[si]
    tpp, slp = r["e"] * tp / 1e4, r["e"] * sl / 1e4
    n = max(1, min(40, round(w / (tpp * 2.0))))
    if s >= 0 and (t < 0 or s <= t):
        p = -slp
    elif t >= 0:
        p = tpp
    else:
        p = max(-slp, side * r["eod"])
    return p * 2.0 * n - n, n


def main():
    sp = sys.argv[1]
    rows = parse([f"{sp}/{x}_tags.txt" for x in ("CBA", "CBB", "CBC", "CBD", "CBE")])
    add_daily(rows)
    reg = rvol()
    rows = [r for r in rows if reg.get(r["date"], 9.0) < 0.30]
    cal = sorted({r["date"] for r in rows})
    first = {}
    for typ, fname, side in RULES:
        for r in rows:
            if r["type"] == typ and FILTERS[fname](r):
                k = r["date"]
                if k not in first or r["hm"] < first[k][0]["hm"]:
                    first[k] = (r, side, typ)
    days = sorted(first)
    print(f"signal days: {len(days)} of {len(cal)} ({len(days)/len(cal)*100:.0f}%), "
          f"{len(days)/8:.0f} per year; by rule: "
          + str(dict(sorted(defaultdict(int, {t: sum(1 for d in days if first[d][2] == t) for _, _, t in [(0, 0, x[0]) for x in RULES]}).items()))))
    for tp, sl, w in ((20, 40, 750.0), (25, 40, 1000.0), (25, 50, 750.0), (30, 50, 1000.0), (40, 60, 1000.0)):
        tr = [Trade(d, res(first[d][0], first[d][1], tp, sl, w)[0], "C") for d in days]
        out = []
        for lo, hi in (("0", SPLIT), (SPLIT, "9")):
            ts = [t for t in tr if lo <= t.date < hi]
            cc = [d for d in cal if lo <= d < hi]
            o = outcomes(calendar_days(ts, cc), flat(1, 1e6), window=160, start_pnl=0.0, target=3000.0, consistency=True)
            p = sum(1 for x, _ in o if x == "pass") / len(o) * 100
            md = sorted(dd for x, dd in o if x == "pass")
            v = [t.points for t in ts]
            out.append(f"WR {sum(x > 0 for x in v)/len(v)*100:3.0f}% ${st.mean(v):+5.0f}/tr pass {p:4.1f}% in {md[len(md)//2] if md else 0:3} d")
        print(f"  TP {tp}bp SL {sl}bp win ${w:.0f}:  2018-21 {out[0]}  |  2022-25 {out[1]}")

    # added to the book at a normal size instead
    c, _ = load_components(sp)
    nq = [Trade(t.date, t.points - 1.0, t.strat) for t in book(c, reg, mnq=1)]
    ym = [Trade(t.date, (t.points * 0.5 - 1.0) * 2, "YM")
          for t in load_tags(f"{sp}/XYM_tags.txt", fmt="s1") if reg.get(t.date, 9.0) < 0.30]
    base = merge(nq, ym)
    combo = []
    for d in days:
        r, side, _ = first[d]
        ti, si = LEVELS.index(25), LEVELS.index(40)
        fav, adv = (r["up"], r["dn"]) if side == 1 else (r["dn"], r["up"])
        t, s = fav[ti], adv[si]
        p = -r["e"] * 0.004 if s >= 0 and (t < 0 or s <= t) else (r["e"] * 0.0025 if t >= 0 else max(-r["e"] * 0.004, side * r["eod"]))
        combo.append((d, p))
    cal2 = sorted(set(t.date for t in base) | set(days))
    for n in (0, 1, 2):
        ts = merge(base, [Trade(d, (p * 2.0 - 1.0) * n, "C") for d, p in combo]) if n else base
        T = staged(calendar_days(ts, cal2), lad(700, 4, 75), lad(800, 4, 75), lad(700, 4, 75))
        stage_line(f"book + combo {n} MNQ/unit", T)
        r = sim_groups([(5, T)])
        print(f"      5 accounts 24m: p10 {r['p10']:,.0f}  median {r['p50']:,.0f}  p90 {r['p90']:,.0f}")


if __name__ == "__main__":
    main()
