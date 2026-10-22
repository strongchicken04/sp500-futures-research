"""Indicator strategies from VIX, VWAP, RSI, EMAs, volume profile, relative
strength and relative volume (multi_feature_exporter), long and short.

Rules are written down before looking at results; each fires at most once a
day (first decision time it holds). Every rule is scored two ways:
  edge     result per trade in bp averaged over a block of brackets
           (target 10-60 bp, stop 1-4x target), so no single lucky bracket
           drives it; t-statistic; 2018-2021 and 2022-2025 separately
  sprint   evaluation attempts with the sprint bracket (+0.20% / -0.40%,
           stop sized to $1,900): pass per attempt and expected trading days
           to a pass, vs the plain 09:31-long sprint (~36%, ~13.5 days)
Finally a logistic model on all features (fit 2018-2020, threshold from 2021,
applied unchanged to 2022-2025).

Usage: score_multi_feature.py SCRATCH_DIR
"""
from __future__ import annotations

import math
import statistics as st
import sys

import numpy as np
from sklearn.linear_model import LogisticRegression

sys.path.insert(0, "scripts")
from prop_sim import Trade  # noqa: E402
from mixed_accounts import calendar_days  # noqa: E402
from final_lifecycle import flat  # noqa: E402
from ladder_sim import outcomes  # noqa: E402

LEVELS = [5, 10, 15, 20, 25, 30, 40, 50, 60, 75, 100, 125, 150]
F = ["ret", "rs", "vwapd", "rsi14", "rsi2", "e9", "e21", "e50", "vix", "vixchg", "vixrel",
     "poc", "vah", "val", "rv30", "_a", "_b"]
CELLS = [(ti, si) for ti in range(len(LEVELS)) for si in range(len(LEVELS))
         if 10 <= LEVELS[ti] <= 60 and LEVELS[ti] <= LEVELS[si] <= 4 * LEVELS[ti]]
COST_BP = 0.5


def parse(path):
    rows = []
    for raw in open(path):
        f = raw.strip().split(",")
        if f[0] != "M" or len(f) < 48:
            continue
        r = {"date": f"{f[1][:4]}-{f[1][4:6]}-{f[1][6:]}", "hm": int(f[2]), "e": float(f[3]),
             "up": [int(x) for x in f[21:34]], "dn": [int(x) for x in f[34:47]], "eod": float(f[47])}
        for k, x in zip(F, f[4:21]):
            r[k] = float(x)
        rows.append(r)
    return rows


def bp(r, side, ti, si):
    fav, adv = (r["up"], r["dn"]) if side == 1 else (r["dn"], r["up"])
    t, s = fav[ti], adv[si]
    if s >= 0 and (t < 0 or s <= t):
        return -LEVELS[si]
    if t >= 0:
        return LEVELS[ti]
    return max(-LEVELS[si], side * r["eod"] / r["e"] * 1e4)


def smooth(r, side):
    return st.mean(bp(r, side, ti, si) for ti, si in CELLS) - COST_BP


def sprint_usd(r, side):
    ti, si = LEVELS.index(20), LEVELS.index(40)
    x = bp(r, side, ti, si)
    S = r["e"] * 0.004
    n = max(1, min(40, int(1900 / (S * 2.0))))
    return (x / 1e4 * r["e"] - 0.5) * 2.0 * n - n


def tstat(v):
    sd = st.pstdev(v) if len(v) > 2 else 0
    return st.mean(v) / sd * math.sqrt(len(v)) if sd > 0 else 0.0


RULES = {
    "trend pullback": lambda r: 1 if (r["vwapd"] > 0 and r["e21"] > 0 and r["e50"] > 0 and 40 <= r["rsi14"] <= 55
                                      and r["rs"] > 0 and r["vixchg"] < 0) else
                     (-1 if (r["vwapd"] < 0 and r["e21"] < 0 and r["e50"] < 0 and 45 <= r["rsi14"] <= 60
                             and r["rs"] < 0 and r["vixchg"] > 0) else 0),
    "momentum confluence": lambda r: 1 if (r["vwapd"] > 0 and r["e9"] > 0 and r["e21"] > 0 and r["e50"] > 0
                                           and r["rsi14"] > 60 and r["rs"] > 0 and r["rv30"] > 1.2
                                           and r["vixchg"] < 0) else
                          (-1 if (r["vwapd"] < 0 and r["e9"] < 0 and r["e21"] < 0 and r["e50"] < 0
                                  and r["rsi14"] < 40 and r["rs"] < 0 and r["rv30"] > 1.2
                                  and r["vixchg"] > 0) else 0),
    "RSI(2) reversion to VWAP": lambda r: 1 if (r["rsi2"] < 10 and r["vwapd"] < -20) else
                               (-1 if (r["rsi2"] > 90 and r["vwapd"] > 20) else 0),
    "value-area acceptance": lambda r: 1 if (r["vah"] > 0 and r["vwapd"] > 0 and r["rs"] > 0) else
                            (-1 if (r["val"] < 0 and r["vwapd"] < 0 and r["rs"] < 0) else 0),
    "VIX regime: calm = fade, stressed = follow":
        lambda r: ((-1 if r["vwapd"] > 25 else (1 if r["vwapd"] < -25 else 0)) if r["vixrel"] < 1.0 else
                   (1 if r["vwapd"] > 25 else (-1 if r["vwapd"] < -25 else 0))),
    "relative strength + VWAP": lambda r: 1 if (r["rs"] > 0.002 and r["vwapd"] > 0) else
                               (-1 if (r["rs"] < -0.002 and r["vwapd"] < 0) else 0),
    "VIX falling + above VWAP and EMA50": lambda r: 1 if (r["vixchg"] < -0.03 and r["vwapd"] > 0 and r["e50"] > 0) else
                                         (-1 if (r["vixchg"] > 0.03 and r["vwapd"] < 0 and r["e50"] < 0) else 0),
}


def first_signals(rows, fn):
    out = {}
    for r in sorted(rows, key=lambda r: (r["date"], r["hm"])):
        if r["date"] in out:
            continue
        s = fn(r)
        if s:
            out[r["date"]] = (r, s)
    return out


def sprint(sig, cal):
    res = []
    for lo, hi in (("0", "2022"), ("2022", "9")):
        trs = [Trade(d, sprint_usd(r, s), "S") for d, (r, s) in sig.items() if lo <= d < hi]
        cc = [c for c in cal if lo <= c < hi]
        o = outcomes(calendar_days(trs, cc), flat(1, 1e6), window=200, start_pnl=0.0, target=3000.0, consistency=True)
        p = sum(1 for x, _ in o if x == "pass") / len(o)
        md = st.mean(d for _, d in o)
        res.append((p * 100, md / p if p else 0))
    return res


def main():
    sp = sys.argv[1]
    rows = parse(f"{sp}/MFEAT_tags.txt")
    cal = sorted({r["date"] for r in rows})
    print(f"{len(rows)} decision points on {len(cal)} days\n")
    print(f"{'rule':<42} {'n/yr':>5} {'long%':>5} | {'bp IS':>6} {'t':>5} | {'bp OOS':>6} {'t':>5} | sprint pass / days to funded")
    for name, fn in RULES.items():
        sig = first_signals(rows, fn)
        a = [smooth(r, s) for d, (r, s) in sig.items() if d < "2022"]
        b = [smooth(r, s) for d, (r, s) in sig.items() if d >= "2022"]
        sp_ = sprint(sig, cal)
        longs = sum(1 for _, (r, s) in sig.items() if s == 1) / max(1, len(sig)) * 100
        print(f"{name:<42} {len(sig)/8:5.0f} {longs:4.0f}% | {st.mean(a):+6.2f} {tstat(a):+5.1f} | "
              f"{st.mean(b):+6.2f} {tstat(b):+5.1f} | {sp_[0][0]:4.1f}% {sp_[0][1]:5.1f}d / {sp_[1][0]:4.1f}% {sp_[1][1]:5.1f}d")

    keys = [k for k in F if not k.startswith("_")] + ["hm"]
    X = np.array([[r[k] for k in keys] for r in rows])
    X = (X - X[np.array([r["date"] < "2021" for r in rows])].mean(0)) / (X.std(0) + 1e-9)
    ti, si = LEVELS.index(20), LEVELS.index(40)
    yl = np.array([bp(r, 1, ti, si) > 0 for r in rows])
    ys = np.array([bp(r, -1, ti, si) > 0 for r in rows])
    d = np.array([r["date"] for r in rows])
    tr = d < "2021"
    ml = LogisticRegression(C=0.3, max_iter=3000).fit(X[tr], yl[tr])
    ms = LogisticRegression(C=0.3, max_iter=3000).fit(X[tr], ys[tr])
    pl, ps = ml.predict_proba(X)[:, 1], ms.predict_proba(X)[:, 1]
    print("\nlogistic model on all features (fit 2018-20):")
    for thr in (0.0, 0.03, 0.06):
        sig = {}
        for i, r in sorted(enumerate(rows), key=lambda x: (x[1]["date"], x[1]["hm"])):
            if r["date"] in sig:
                continue
            if pl[i] - ps[i] > thr:
                sig[r["date"]] = (r, 1)
            elif ps[i] - pl[i] > thr:
                sig[r["date"]] = (r, -1)
        b = [smooth(r, s) for dd, (r, s) in sig.items() if dd >= "2022"]
        v = [smooth(r, s) for dd, (r, s) in sig.items() if "2021" <= dd < "2022"]
        sp_ = sprint(sig, cal)
        print(f"   margin {thr:.2f}: 2021 {st.mean(v):+.2f} bp | 2022-25 {st.mean(b):+.2f} bp t{tstat(b):+.1f} "
              f"({len(b)/4:.0f}/yr) | sprint 2022-25 {sp_[1][0]:.1f}% {sp_[1][1]:.1f}d")
    print("   long-model weights:", {k: round(w, 2) for k, w in zip(keys, ml.coef_[0])})


if __name__ == "__main__":
    main()
