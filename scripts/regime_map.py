"""Regime map for the live strategies (system manager).

For each live strategy, results by market regime, separately for 2018-2021
and 2022-2025, so a regime filter counts only if it holds in both halves:
  VIX at 10:00          <15, 15-20, 20-25, >=25
  realised vol (20d)    terciles with cut-offs fixed on 2018-2021
  trend                 15:55 close above / below its 50-day average
  weekday
Regime inputs are built from MFEAT (NQ price and VIX at 10:00, 15:55 close)
using only data up to the prior day (VIX at 10:00 the same day, known then).

Strategies (NQ points per MNQ, costs included as in their scorers):
  RS sprint   relative strength + VWAP (0.15%), sprint bracket +0.20/-0.40%, bp
  noise       noise-area momentum (score_noise_tod.z_result)
  VWAP band   20 bp band, SL 25 / TP 100 (load_components 'vg')
  ORB         15-minute ORB long with the fill fix (load_components 's1')

Usage: regime_map.py FIXED_DIR
"""
from __future__ import annotations

import datetime as dt
import math
import statistics as st
import sys

sys.path.insert(0, "scripts")
from rescore_all import load_components  # noqa: E402
from score_noise_tod import parse as parse_noise, z_result  # noqa: E402
from score_multi_feature import parse as parse_mf, first_signals, bp, LEVELS  # noqa: E402


def regimes(rows):
    """date -> {vix, rv, trend} with rv/trend from prior days only."""
    day = {}
    for r in sorted(rows, key=lambda r: (r["date"], r["hm"])):
        d = day.setdefault(r["date"], {})
        if r["hm"] == 600:
            d["vix"] = r["vix"]
        d["close"] = r["e"] + r["eod"]          # same 15:55 close from every check
    dates = sorted(day)
    out = {}
    for i, d in enumerate(dates):
        if i < 51 or "vix" not in day[d]:
            continue
        cl = [day[x]["close"] for x in dates[i - 51:i]]
        rets = [cl[j] / cl[j - 1] - 1 for j in range(31, 51)]
        rv = st.pstdev(rets) * math.sqrt(252)
        out[d] = {"vix": day[d]["vix"], "rv": rv, "trend": 1 if cl[-1] > sum(cl[1:]) / 50 else -1,
                  "wd": dt.date.fromisoformat(d).weekday()}
    return out


def stat(v):
    if len(v) < 5:
        return f"{'':>7} {'':>5} {len(v):>4}"
    sd = st.pstdev(v)
    t = st.mean(v) / sd * math.sqrt(len(v)) if sd else 0
    return f"{st.mean(v):+7.2f} {t:+5.1f} {len(v):>4}"


def main():
    sp = sys.argv[1]
    mf = parse_mf(f"{sp}/MFEAT_tags.txt")
    reg = regimes(mf)
    rv_is = sorted(r["rv"] for d, r in reg.items() if d < "2022")
    c1, c2 = rv_is[len(rv_is) // 3], rv_is[2 * len(rv_is) // 3]

    rs = first_signals(mf, lambda r: 1 if (r["rs"] > 0.0015 and r["vwapd"] > 0) else
                       (-1 if (r["rs"] < -0.0015 and r["vwapd"] < 0) else 0))
    ti, si = LEVELS.index(20), LEVELS.index(40)
    strat = {"RS sprint (bp)": [(d, bp(r, s, ti, si) - 0.5) for d, (r, s) in rs.items()]}
    Z, _ = parse_noise(f"{sp}/NOISETOD_tags.txt")
    strat["noise (pt)"] = [(f"{z['ymd'][:4]}-{z['ymd'][4:6]}-{z['ymd'][6:]}", z_result(z)) for z in Z]
    c, _ = load_components(sp)
    strat["VWAP band (pt)"] = [(t.date, t.points - 0.5) for t in c["vg"]]
    strat["ORB (pt)"] = [(t.date, t.points - 0.5) for t in c["s1"]]

    buckets = {
        "VIX <15": lambda g: g["vix"] < 15, "VIX 15-20": lambda g: 15 <= g["vix"] < 20,
        "VIX 20-25": lambda g: 20 <= g["vix"] < 25, "VIX >=25": lambda g: g["vix"] >= 25,
        f"rv low (<{c1:.2f})": lambda g: g["rv"] < c1, "rv mid": lambda g: c1 <= g["rv"] < c2,
        f"rv high (>={c2:.2f})": lambda g: g["rv"] >= c2,
        "rv >= 0.30 (gated out)": lambda g: g["rv"] >= 0.30,
        "trend up": lambda g: g["trend"] == 1, "trend down": lambda g: g["trend"] == -1,
    }
    for i, n in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri"]):
        buckets[n] = (lambda k: lambda g: g["wd"] == k)(i)

    print(f"regime days: {len(reg)}; rv terciles (2018-21) {c1:.3f} / {c2:.3f}\n")
    for name, ts in strat.items():
        ts = [(d, x) for d, x in ts if d in reg]
        print(f"== {name}: all {stat([x for d, x in ts if d < '2022'])} | {stat([x for d, x in ts if d >= '2022'])}")
        print(f"   {'regime':<22} {'2018-21 mean   t    n':>22} | {'2022-25 mean   t    n':>22}")
        for b, fn in buckets.items():
            a = [x for d, x in ts if d < "2022" and fn(reg[d])]
            z = [x for d, x in ts if d >= "2022" and fn(reg[d])]
            print(f"   {b:<22} {stat(a):>22} | {stat(z):>22}")
        years = sorted({d[:4] for d, _ in ts})
        print("   by year: " + "  ".join(f"{y} {st.mean([x for d, x in ts if d[:4] == y]):+.1f}" for y in years))
        print()


if __name__ == "__main__":
    main()
