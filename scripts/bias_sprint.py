"""Daily bias for the evaluation sprint: long or short at 09:31?

The sprint trade (entry at the close of the 09:30-09:31 bar, target +0.20%,
stop -0.40% in the bias direction, flat at 15:55) is taken long or short
according to a bias known before the entry. Inputs, all available by 09:31:
  trend      prior close vs its 20/50/200-day averages, 5- and 20-day returns
  yesterday  prior-day return and where it closed in its range
  overnight  gap (09:30 open vs prior close), where 09:31 sits in the
             overnight range, the premarket move 08:00 -> 09:31
  volatility 20-day realised volatility
Single rules and a majority vote are fixed in advance; a logistic model is
fitted on 2018-2020, its threshold set on 2021, and it is applied unchanged to
2022-2025. Every bias is compared with 'always long' (which rides NQ's drift)
and with the random-walk win rate of the bracket (67%).

Usage: bias_sprint.py SCRATCH_DIR
"""
from __future__ import annotations

import math
import statistics as st
import sys

import numpy as np
from sklearn.linear_model import LogisticRegression

sys.path.insert(0, "scripts")
from prop_sim import Trade  # noqa: E402
from rescore_all import rvol  # noqa: E402
from mixed_accounts import calendar_days  # noqa: E402
from final_lifecycle import flat  # noqa: E402
from ladder_sim import outcomes  # noqa: E402
from score_cond_bracket import parse, add_daily, LEVELS  # noqa: E402

TI, SI = LEVELS.index(20), LEVELS.index(40)
FEE = 90.0


def outcome(r, side):
    fav, adv = (r["up"], r["dn"]) if side == 1 else (r["dn"], r["up"])
    t, s = fav[TI], adv[SI]
    T, S = r["e"] * 0.0020, r["e"] * 0.0040
    if s >= 0 and (t < 0 or s <= t):
        p = -S - 0.25
    elif t >= 0:
        p = T
    else:
        p = max(-S - 0.25, side * r["eod"] - 0.25)
    n = max(1, min(40, int(1900 / (S * 2.0))))
    return (p - 0.25) * 2.0 * n - n


def build(sp):
    rows = [r for r in parse([f"{sp}/CBA_tags.txt"]) if r["type"] == "T931"]
    add_daily(rows)
    pre = {}
    for r in parse([f"{sp}/ONITE_NQ_tags.txt"]):
        if r["type"] == "T800":
            pre[r["date"]] = r["e"]
    closes = {r["date"]: r["pc"] for r in rows}
    dates = sorted(closes)
    idx = {d: i for i, d in enumerate(dates)}
    reg = rvol()
    out = []
    for r in rows:
        i = idx[r["date"]]
        if i < 60 or r["date"] not in pre:
            continue
        hist = [closes[dates[j]] for j in range(i - 60, i + 1)]   # prior closes, last = r["pc"]
        pc = r["pc"]
        f = {
            "sma20": pc / st.mean(hist[-20:]) - 1, "sma50": pc / st.mean(hist[-50:]) - 1,
            "sma200": (pc / r["sma"] - 1) if r["sma"] else 0.0,
            "ret5": pc / hist[-6] - 1, "ret20": pc / hist[-21] - 1,
            "prev": r["prev"] or 0.0,
            "cloc": (pc - r["pdl"]) / (r["pdh"] - r["pdl"]) - 0.5 if r["pdh"] > r["pdl"] else 0.0,
            "gap": r["gap"],
            "onpos": (r["e"] - r["onl"]) / (r["onh"] - r["onl"]) - 0.5 if r["onh"] > r["onl"] else 0.0,
            "pre": r["e"] / pre[r["date"]] - 1,
            "vol": reg.get(r["date"], 0.2),
        }
        out.append((r, f))
    return out


def evaluate(name, pairs, side_fn, cal):
    res = {}
    for lo, hi in (("0", "2022"), ("2022", "9")):
        trs, w = [], []
        for r, f in pairs:
            if not (lo <= r["date"] < hi):
                continue
            side = side_fn(r, f)
            if side == 0:
                continue
            x = outcome(r, side)
            trs.append(Trade(r["date"], x, "S"))
            w.append(x > 0)
        cc = [c for c in cal if lo <= c < hi]
        o = outcomes(calendar_days(trs, cc), flat(1, 1e6), window=200, start_pnl=0.0, target=3000.0, consistency=True)
        p = sum(1 for x, _ in o if x == "pass") / len(o)
        md = st.mean(d for _, d in o)
        res[lo] = (sum(w) / len(w) * 100, p * 100, md / p if p else 0, len(trs))
    a, b = res["0"], res["2022"]
    print(f"{name:<38} WR {a[0]:4.1f}% / {b[0]:4.1f}%   pass/attempt {a[1]:4.1f}% / {b[1]:4.1f}%   "
          f"days to funded {a[2]:5.1f} / {b[2]:5.1f}")


def main():
    sp = sys.argv[1]
    pairs = build(sp)
    cal = sorted({r["date"] for r, _ in pairs})
    print(f"{len(pairs)} days; bracket +0.20% / -0.40% (random-walk win rate 67%); 2018-21 / 2022-25\n")
    sgn = lambda x: 1 if x > 0 else -1
    rules = {
        "always long": lambda r, f: 1,
        "always short": lambda r, f: -1,
        "trend: above 20-day average": lambda r, f: sgn(f["sma20"]),
        "trend: above 50-day average": lambda r, f: sgn(f["sma50"]),
        "trend: above 200-day average": lambda r, f: sgn(f["sma200"]),
        "momentum: 5-day return": lambda r, f: sgn(f["ret5"]),
        "reversal: against yesterday": lambda r, f: -sgn(f["prev"]),
        "gap continuation": lambda r, f: sgn(f["gap"]),
        "gap fade": lambda r, f: -sgn(f["gap"]),
        "premarket 08:00-09:31 momentum": lambda r, f: sgn(f["pre"]),
        "upper/lower half of overnight range": lambda r, f: sgn(f["onpos"]),
        "vote: 50d + 20d + 5d + premarket + ON": lambda r, f: sgn(sgn(f["sma50"]) + sgn(f["sma20"]) + sgn(f["ret5"])
                                                                   + sgn(f["pre"]) + sgn(f["onpos"])),
        "trend 50d, skip if premarket disagrees": lambda r, f: sgn(f["sma50"]) if sgn(f["pre"]) == sgn(f["sma50"]) else 0,
    }
    for name, fn in rules.items():
        evaluate(name, pairs, fn, cal)

    # logistic model: P(long bracket wins) and P(short bracket wins)
    keys = list(pairs[0][1].keys())
    X = np.array([[f[k] for k in keys] for _, f in pairs]) * 100
    yl = np.array([outcome(r, 1) > 0 for r, _ in pairs])
    ys = np.array([outcome(r, -1) > 0 for r, _ in pairs])
    d = np.array([r["date"] for r, _ in pairs])
    tr = d < "2021"
    ml = LogisticRegression(C=0.5, max_iter=2000).fit(X[tr], yl[tr])
    ms = LogisticRegression(C=0.5, max_iter=2000).fit(X[tr], ys[tr])
    pl, ps = ml.predict_proba(X)[:, 1], ms.predict_proba(X)[:, 1]
    edge = {r["date"]: (pl[i], ps[i]) for i, (r, _) in enumerate(pairs)}
    for thr in (0.0, 0.02, 0.05):
        fn = (lambda r, f, t=thr: 1 if edge[r["date"]][0] - edge[r["date"]][1] > t
              else (-1 if edge[r["date"]][1] - edge[r["date"]][0] > t else 0))
        evaluate(f"logistic model (fit 2018-20), margin {thr:.2f}", pairs, fn, cal)
    print("\nlogistic weights (long model):", {k: round(w, 3) for k, w in zip(keys, ml.coef_[0])})


if __name__ == "__main__":
    main()
