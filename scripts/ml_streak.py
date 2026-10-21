"""Can a model pick trades that win ~80% at reward:risk 1:1.5?

Every entry from the conditional bracket exports (fixed times, ORB, VWAP band,
prior-day and overnight levels, opening candle, first-hour range, noise area,
value area, midday, 15:00), both directions, becomes one sample. The label is
whether the bracket (target T bp, stop 1.5 T bp) wins. Features are only what
is known at entry: entry type and time, weekday, gap, prior-day return,
distance to the 200-day average, and the distance from the entry price to
VWAP, the prior-day high/low, the overnight high/low and the opening range,
plus the widths of those ranges and the 20-day volatility.

A gradient-boosted classifier is trained on 2018-2020, the probability
threshold is chosen on 2021, and everything is then frozen and applied to
2022-2025. On each day only the single most confident trade is taken, and
only if it clears the threshold. The random-walk win rate at 1:1.5 is 60%.
"""
from __future__ import annotations

import sys

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier

sys.path.insert(0, "scripts")
from rescore_all import rvol  # noqa: E402
from score_cond_bracket import parse, add_daily, LEVELS  # noqa: E402
from streak_scan import win  # noqa: E402

BRACKETS = [(20, 30), (40, 60)]


def bp(a, b):
    return (a - b) / b * 1e4 if a and b else np.nan


def features(r, side, types, reg):
    e = r["e"]
    f = [types.index(r["type"]), side, r["hm"], int(r["date"][8:10]) % 7,
         r["gap"] * 1e4, (r["prev"] or 0.0) * 1e4,
         bp(r["pc"], r["sma"]) if r["sma"] else np.nan,
         bp(e, r["vwap"]), bp(e, r["pdh"]), bp(e, r["pdl"]),
         bp(e, r["onh"]) if r["onh"] > 0 else np.nan, bp(e, r["onl"]) if r["onl"] > 0 else np.nan,
         bp(e, r["orh"]) if r["orh"] > 0 else np.nan, bp(e, r["orl"]) if r["orl"] > 0 else np.nan,
         bp(r["pdh"], r["pdl"]), bp(r["onh"], r["onl"]) if r["onl"] > 0 else np.nan,
         bp(r["orh"], r["orl"]) if r["orl"] > 0 else np.nan, reg.get(r["date"], np.nan)]
    return [side * x if i in (4, 5, 6, 7, 8, 9, 10, 11, 12, 13) and x == x else x for i, x in enumerate(f)]


def main():
    sp = sys.argv[1]
    rows = parse([f"{sp}/{x}_tags.txt" for x in ("CBA", "CBB", "CBC", "CBD", "CBE")])
    add_daily(rows)
    reg = rvol()
    types = sorted({r["type"] for r in rows})
    for tp, sl in BRACKETS:
        ti, si = LEVELS.index(tp), LEVELS.index(sl)
        X, y, dates = [], [], []
        for r in rows:
            for side in (1, -1):
                X.append(features(r, side, types, reg))
                y.append(1 if win(r, side, ti, si) else 0)
                dates.append(r["date"])
        X, y, dates = np.array(X, float), np.array(y), np.array(dates)
        tr, va, te = dates < "2021", (dates >= "2021") & (dates < "2022"), dates >= "2022"
        clf = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=300,
                                             min_samples_leaf=200, l2_regularization=1.0,
                                             categorical_features=[0], random_state=0)
        clf.fit(X[tr], y[tr])
        p = clf.predict_proba(X)[:, 1]
        print(f"\n== bracket TP {tp} bp / SL {sl} bp (random walk {sl/(tp+sl)*100:.0f}%), {len(y)} samples")
        print(f"   base win rate: train {y[tr].mean()*100:.1f}%  2021 {y[va].mean()*100:.1f}%  2022-25 {y[te].mean()*100:.1f}%")

        def best_per_day(mask, thr):
            best = {}
            for i in np.where(mask & (p >= thr))[0]:
                d = dates[i]
                if d not in best or p[i] > p[best[d]]:
                    best[d] = i
            idx = list(best.values())
            return (y[idx].mean() if idx else np.nan), len(idx)

        print(f"   {'threshold':>9} {'2021 WR':>8} {'n':>5} | {'2022-25 WR':>10} {'n/yr':>5} {'2 in a row':>10} {'3 in a row':>10}")
        for thr in (0.60, 0.65, 0.70, 0.75, 0.80, 0.85):
            wv, nv = best_per_day(va, thr)
            wt, nt = best_per_day(te, thr)
            if nt == 0:
                continue
            print(f"   {thr:9.2f} {wv*100:7.1f}% {nv:5} | {wt*100:9.1f}% {nt/4:5.0f} {wt**2*100:9.1f}% {wt**3*100:9.1f}%")


if __name__ == "__main__":
    main()
