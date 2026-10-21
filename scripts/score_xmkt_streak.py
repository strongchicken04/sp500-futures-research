"""Win-streak search across markets: which signals beat the random-walk
win rate by the most, and does stacking them reach a 65-70% evaluation pass?

Reads G tags from the cross-market exporter (ES, YM, RTY, GC, CL, ZN) and the
NQ level/first-hour/noise/midday exports. For every market x entry type x
context filter (one or two) x direction x bracket with reward:risk between
1:1.5 and 1:3.3, the win rate is compared with the random-walk rate
stop/(target+stop). Costs per trade are a commission of 0.3 bp plus one tick
on entry and one more on a stop, in basis points of that market's price.

Selection uses 2018-2021 only: a rule must beat the random rate by at least
MIN_EDGE in 2018-2019 AND in 2020-2021 separately (20+ trades in each). Ranking
on the best 2018-2021 edge alone, tried first, picked mostly luck: its stacks
passed 74-84% in 2018-2021 and 28-39% in 2022-2025. The selected rules are then stacked
(one trade a day, the earliest signal), sized so a win is $600 and a loss is
$600 x reward:risk, and the evaluation is simulated on 2018-2021 and, with
nothing changed, on 2022-2025.
"""
from __future__ import annotations

import itertools
import os
import statistics as st
import sys
from collections import defaultdict

sys.path.insert(0, "scripts")
from prop_sim import Trade  # noqa: E402
from mixed_accounts import calendar_days  # noqa: E402
from final_lifecycle import flat  # noqa: E402
from ladder_sim import outcomes  # noqa: E402
from score_cond_bracket import parse, add_daily, FILTERS, LEVELS  # noqa: E402

TICK_BP = {"NQ": 0.17, "ES": 0.6, "YM": 0.3, "RTY": 0.5, "GC": 0.5, "CL": 1.4, "ZN": 1.4}
COMM_BP = 0.3
PAIRS = [(ti, si) for ti in range(len(LEVELS)) for si in range(len(LEVELS))
         if 1.5 <= LEVELS[si] / LEVELS[ti] <= 3.34]
MIN_EDGE = 0.08
WIN_USD = 600.0
NQ_TYPES = {"PDL", "PDH", "ONL", "ONH", "IBU", "IBD", "NZU", "NZD", "MDU", "MDD"}


def load(sp):
    rows = []
    for inst in ("ES", "YM", "RTY", "GC", "CL", "ZN"):
        p = f"{sp}/XM_{inst}_tags.txt"
        if os.path.exists(p):
            rs = parse([p])
            add_daily(rs)
            for r in rs:
                r["inst"] = inst
            rows += rs
    rs = parse([f"{sp}/{x}_tags.txt" for x in ("CBC", "CBD", "CBE")])
    add_daily(rs)
    for r in rs:
        r["inst"] = "NQ"
    rows += [r for r in rs if r["type"] in NQ_TYPES]
    return rows


def result_bp(r, side, ti, si):
    """Signed result in bp after costs, and whether it is a win."""
    fav, adv = (r["up"], r["dn"]) if side == 1 else (r["dn"], r["up"])
    t, s = fav[ti], adv[si]
    tick = TICK_BP[r["inst"]]
    if s >= 0 and (t < 0 or s <= t):
        x = -LEVELS[si] - tick
    elif t >= 0:
        x = LEVELS[ti]
    else:
        x = max(-LEVELS[si] - tick, side * r["eod"] / r["e"] * 1e4 - tick)
    x -= COMM_BP + tick
    return x, x > 0


def evaluate(trades, cal, lo, hi):
    ts = [t for t in trades if lo <= t.date < hi]
    cc = [d for d in cal if lo <= d < hi]
    o = outcomes(calendar_days(ts, cc), flat(1, 1e6), window=160, start_pnl=0.0, target=3000.0, consistency=True)
    p = sum(1 for x, _ in o if x == "pass") / len(o) * 100
    md = sorted(dd for x, dd in o if x == "pass")
    v = [t.points for t in ts]
    wr = sum(1 for x in v if x > 0) / len(v) * 100 if v else 0
    return p, (md[len(md) // 2] if md else 0), wr, len(v)


def main():
    sp = sys.argv[1]
    rows = load(sp)
    print(f"{len(rows)} entries; markets {sorted({r['inst'] for r in rows})}")
    fl = [f for f in FILTERS if f != "all"]
    combos = [("all",)] + [(f,) for f in fl] + list(itertools.combinations(fl, 2))
    groups = defaultdict(list)
    for r in rows:
        groups[(r["inst"], r["type"])].append(r)
    found = []
    for (inst, typ), rs in sorted(groups.items()):
        for cb in combos:
            sel = [r for r in rs if all(FILTERS[f](r) for f in cb)]
            a = [r for r in sel if r["date"] < "2022"]
            b = [r for r in sel if r["date"] >= "2022"]
            if len(a) < 40 or len(b) < 15:
                continue
            for side in (1, -1):
                for ti, si in PAIRS:
                    base = LEVELS[si] / (LEVELS[ti] + LEVELS[si])
                    a1 = [r for r in a if r["date"] < "2020"]
                    a2 = [r for r in a if r["date"] >= "2020"]
                    if len(a1) < 20 or len(a2) < 20:
                        continue
                    w1 = st.mean(result_bp(r, side, ti, si)[1] for r in a1)
                    w2 = st.mean(result_bp(r, side, ti, si)[1] for r in a2)
                    if min(w1, w2) - base < MIN_EDGE:
                        continue
                    wa = st.mean(result_bp(r, side, ti, si)[1] for r in a)
                    wb = st.mean(result_bp(r, side, ti, si)[1] for r in b)
                    found.append((wa - base, wb - base, inst, typ, cb, side, ti, si, base, wa, wb, sel))
    found.sort(key=lambda x: -x[0])
    print(f"{len(found)} rules beat random by >= {MIN_EDGE*100:.0f} pp in both 2018-19 and 2020-21\n")
    print("top 30 by 2018-21 edge (2022-25 untouched):")
    for ea, eb, inst, typ, cb, side, ti, si, base, wa, wb, sel in found[:30]:
        print(f"   {inst:<3} {typ:<4} {'L' if side == 1 else 'S'} [{' & '.join(cb)}] TP {LEVELS[ti]} SL {LEVELS[si]}  "
              f"random {base*100:.0f}%  WR {wa*100:.0f}% / {wb*100:.0f}%  edge {ea*100:+.0f} / {eb*100:+.0f} pp  "
              f"({len(sel)/8:.0f}/yr)")
    kept_b = [f for f in found if f[1] >= MIN_EDGE]
    print(f"\nof these, still >= {MIN_EDGE*100:.0f} pp in 2022-25: {len(kept_b)} "
          f"({len(kept_b)/max(1,len(found))*100:.0f}%)")

    # stack: best rule per (market, type, side) chosen on 2018-21 only
    best = {}
    for f in found:
        k = (f[2], f[3], f[5])
        if k not in best:
            best[k] = f
    cal = sorted({r["date"] for r in rows})
    for top in (5, 10, 20, 40):
        rules = sorted(best.values(), key=lambda x: -x[0])[:top]
        first = {}
        for ea, eb, inst, typ, cb, side, ti, si, base, wa, wb, sel in rules:
            ratio = LEVELS[si] / LEVELS[ti]
            for r in sel:
                if r["date"] not in first or r["hm"] < first[r["date"]][0]:
                    x, _ = result_bp(r, side, ti, si)
                    first[r["date"]] = (r["hm"], x / LEVELS[ti] * WIN_USD, ratio)
        trades = [Trade(d, v[1], "S") for d, v in first.items() if v[2] * WIN_USD <= 1950]
        a = evaluate(trades, cal, "0", "2022")
        b = evaluate(trades, cal, "2022", "9")
        print(f"stack of the top {top:2} rules: {len(trades)/8:4.0f} trades/yr | 2018-21 WR {a[2]:.0f}% pass {a[0]:.1f}% "
              f"in {a[1]} d | 2022-25 WR {b[2]:.0f}% pass {b[0]:.1f}% in {b[1]} d")


if __name__ == "__main__":
    main()
