"""Search signal x filter x bracket for the fastest, most likely eval pass.

Reads the conditional bracket exporter (modes A, B, C). Every combination of
entry type, one context filter, direction and bracket (target and stop in
basis points, a win sized at $500-$1,450, stop inside the $2,000 line, at most
40 MNQ, $1 cost per MNQ) becomes one trade on each day the signal fires. The
volatility gate is always on. Pass rate is simulated with the account rules
on the real calendar, starting on every day in turn.

A rule is ranked on 2018-2021 only and its 2022-2025 pass rate is reported
untouched. The bar to clear is the ~40% a purely random entry with the best
bracket reaches (score_bracket.py), not zero.
"""
from __future__ import annotations

import statistics as st
import sys
from collections import defaultdict

sys.path.insert(0, "scripts")
from prop_sim import Trade  # noqa: E402
from rescore_all import rvol  # noqa: E402
from mixed_accounts import calendar_days  # noqa: E402
from final_lifecycle import flat  # noqa: E402
from ladder_sim import outcomes  # noqa: E402

LEVELS = [5, 10, 15, 20, 25, 30, 40, 50, 60, 75, 100, 125, 150]
SPLIT = "2022-01-01"
COST = 1.0
MAX_MNQ = 40
MAX_LOSS = 1950.0
WINS = (500.0, 750.0, 1000.0, 1450.0)


def parse(paths):
    rows = []
    for p in paths:
        for line in open(p):
            f = line.strip().split(",")
            if f[0] != "G" or len(f) < 41:
                continue
            d = f[1]
            x = list(map(float, f[4:14]))
            rows.append({"date": f"{d[:4]}-{d[4:6]}-{d[6:]}", "type": f[2], "hm": int(f[3]),
                         "e": x[0], "pc": x[1], "pdh": x[2], "pdl": x[3], "o930": x[4],
                         "onh": x[5], "onl": x[6], "vwap": x[7], "orh": x[8], "orl": x[9],
                         "up": [int(v) for v in f[14:27]], "dn": [int(v) for v in f[27:40]],
                         "eod": float(f[40])})
    return rows


def add_daily(rows):
    pcs = {}
    for r in rows:
        pcs[r["date"]] = r["pc"]
    dates = sorted(pcs)
    sma, prev = {}, {}
    for i, d in enumerate(dates):
        if i >= 200:
            sma[d] = st.mean(pcs[x] for x in dates[i - 200:i])
        if i >= 1:
            prev[d] = pcs[d] / pcs[dates[i - 1]] - 1.0
    for r in rows:
        r["sma"] = sma.get(r["date"])
        r["prev"] = prev.get(r["date"])
        r["gap"] = r["o930"] / r["pc"] - 1.0


FILTERS = {
    "all": lambda r: True,
    "gap down >=0.25%": lambda r: r["gap"] <= -0.0025,
    "gap up >=0.25%": lambda r: r["gap"] >= 0.0025,
    "gap small": lambda r: abs(r["gap"]) < 0.0025,
    "above 200d": lambda r: r["sma"] is not None and r["pc"] > r["sma"],
    "below 200d": lambda r: r["sma"] is not None and r["pc"] < r["sma"],
    "after down day": lambda r: r["prev"] is not None and r["prev"] < 0,
    "after up day": lambda r: r["prev"] is not None and r["prev"] > 0,
    "above VWAP": lambda r: r["e"] > r["vwap"],
    "below VWAP": lambda r: r["e"] < r["vwap"],
    "inside ON range": lambda r: r["onl"] <= r["e"] <= r["onh"],
}


def trade(r, side, ti, si, w):
    fav, adv = (r["up"], r["dn"]) if side == 1 else (r["dn"], r["up"])
    t, s = fav[ti], adv[si]
    tp = r["e"] * LEVELS[ti] / 1e4
    sl = r["e"] * LEVELS[si] / 1e4
    n = max(1, min(MAX_MNQ, round(w / (tp * 2.0))))
    if s >= 0 and (t < 0 or s <= t):
        pts = -sl
    elif t >= 0:
        pts = tp
    else:
        pts = max(-sl, side * r["eod"])
    return pts * 2.0 * n - COST * n


def pass_rate(trs, cal):
    d = calendar_days(trs, cal)
    o = outcomes(d, flat(1, 1e6), window=120, start_pnl=0.0, target=3000.0, consistency=True)
    if not o:
        return 0.0, 0
    p = sum(1 for x, _ in o if x == "pass") / len(o) * 100
    md = sorted(dd for x, dd in o if x == "pass")
    return p, (md[len(md) // 2] if md else 0)


def main():
    rows = parse(sys.argv[1:])
    add_daily(rows)
    reg = rvol()
    rows = [r for r in rows if reg.get(r["date"], 9.0) < 0.30]
    cal_is = sorted({r["date"] for r in rows if r["date"] < SPLIT})
    cal_oos = sorted({r["date"] for r in rows if r["date"] >= SPLIT})
    by_type = defaultdict(list)
    for r in rows:
        by_type[r["type"]].append(r)
    res = []
    for typ, rs in sorted(by_type.items()):
        for fname, flt in FILTERS.items():
            sel = [r for r in rs if flt(r)]
            n_is = sum(1 for r in sel if r["date"] < SPLIT)
            if n_is < 60:
                continue
            for side in (1, -1):
                for w in WINS:
                    for ti in range(len(LEVELS)):
                        for si in range(ti, len(LEVELS)):
                            if LEVELS[si] / LEVELS[ti] * w > MAX_LOSS:
                                break
                            trs = [Trade(r["date"], trade(r, side, ti, si, w), typ) for r in sel]
                            p_is, _ = pass_rate([t for t in trs if t.date < SPLIT], cal_is)
                            res.append((p_is, typ, fname, side, w, ti, si, trs))
    res.sort(key=lambda x: -x[0])
    print(f"{len(res)} rules searched; top 25 by 2018-21 pass rate, with 2022-25 untouched\n")
    print(f"{'signal':<6} {'filter':<17} {'dir':<5} {'win$':>5} {'TP':>4} {'SL':>4} {'WR':>5} "
          f"{'$/d IS':>7} {'$/d OOS':>7} {'n/yr':>5} {'pass IS':>8} {'pass OOS':>9} {'days':>5}")
    for p_is, typ, fname, side, w, ti, si, trs in res[:25]:
        p_oos, md = pass_rate([t for t in trs if t.date >= SPLIT], cal_oos)
        v = [t.points for t in trs]
        wr = sum(1 for x in v if x > 0) / len(v) * 100
        e_is = st.mean([t.points for t in trs if t.date < SPLIT])
        o = [t.points for t in trs if t.date >= SPLIT]
        e_oos = st.mean(o) if o else 0.0
        print(f"{typ:<6} {fname:<17} {'LONG' if side == 1 else 'SHORT':<5} {w:5.0f} {LEVELS[ti]:4} {LEVELS[si]:4} "
              f"{wr:4.0f}% {e_is:+7.0f} {e_oos:+7.0f} {len(v)/8:5.0f} {p_is:7.1f}% {p_oos:8.1f}% {md:5}")


if __name__ == "__main__":
    main()
