"""09:31 eval sprint (Lucid 7) re-test and regime study (owner request
2026-11-04; rules fixed before results unless marked post-hoc).

Data: T931 rows (entry at the 09:31 close, first-touch bracket levels to
15:55) from CBA_OLD (2010-17), CBA (2018-25), CBA26 (2026 Jan-Jul).
Daily series from each row's prior-day close / high / low (known at 09:31).

Part A - re-test: bias = prior close vs SMA(n) of prior closes (n = 5, 10, 20,
50 = Lucid 7, 100, 200), always long, and a coin flip; bracket +0.20 / -0.40
(Lucid 7) and +0.25 / -0.40. Resolved win rate (target before stop) minus the
random-walk rate S / (T + S), mean gross bp incl. unresolved, by era + 2026.
Then the evaluation itself (50K, INTRA, NQ 28,530, eval_25k.attempt): days and
fees to a pass for SMA50 vs always long vs coin flip.

Part B - when does the SMA50 sprint win? Trades split by the daily regime
before the day:
  ER20  Kaufman efficiency ratio of the last 20 closes (|net move| / path):
        chop < 0.20, mid, trend >= 0.35
  ADX14 (Wilder, daily H/L/C): chop < 20, mid, trend >= 25
  DIST  |prior close / SMA50 - 1|: near < 1%, mid, far >= 3%
Part C - owner's idea (POST-HOC, a grid): in chop (ER20 < 0.20 or ADX < 20)
use a faster SMA (5 / 10 / 20), else SMA50.
Usage: eval931_regimes.py DATA_DIR
"""
from __future__ import annotations

import hashlib
import math
import statistics as st
import sys

sys.path.insert(0, "scripts")
import eval_25k as E  # noqa: E402
import two_win_sprint as W  # noqa: E402
from score_cond_bracket import parse, LEVELS as CL  # noqa: E402

ERAS = (("2010-13", "2010", "2014"), ("2014-17", "2014", "2018"), ("2018-21", "2018", "2022"),
        ("2022-25", "2022", "2026"), ("2026", "2026", "2027"))


def load(data):
    rows = {}
    for f in ("CBA_OLD", "CBA26", "CBA"):            # CBA last: wins the 2025 overlap
        for r in parse([f"{data}/{f}_tags.txt"]):
            if r["type"] == "T931":
                rows[r["date"]] = r
    return [rows[d] for d in sorted(rows)]


def features(rows):
    """Per row index: prior-close SMAs, ER20, ADX14, DIST (all from prior days)."""
    pc = [r["pc"] for r in rows]
    hi = [r["pdh"] for r in rows]
    lo = [r["pdl"] for r in rows]
    n = len(rows)
    out = [dict() for _ in range(n)]
    for i in range(n):
        for k in (5, 10, 20, 50, 100, 200):
            if i >= k - 1:
                out[i][f"sma{k}"] = sum(pc[i - k + 1:i + 1]) / k
        if i >= 20:
            path = sum(abs(pc[j] - pc[j - 1]) for j in range(i - 19, i + 1))
            out[i]["er20"] = abs(pc[i] - pc[i - 20]) / path if path > 0 else 0.0
    # ADX14 on the prior-day bars (bar i = the day before row i)
    tr = [0.0] * n; pdm = [0.0] * n; ndm = [0.0] * n
    for i in range(1, n):
        tr[i] = max(hi[i] - lo[i], abs(hi[i] - pc[i - 1]), abs(lo[i] - pc[i - 1]))
        up, dn = hi[i] - hi[i - 1], lo[i - 1] - lo[i]
        pdm[i] = up if up > dn and up > 0 else 0.0
        ndm[i] = dn if dn > up and dn > 0 else 0.0
    atr = sp = sn = adx = None
    for i in range(1, n):
        if i < 15:
            continue
        if atr is None:
            atr, sp, sn = sum(tr[i - 13:i + 1]), sum(pdm[i - 13:i + 1]), sum(ndm[i - 13:i + 1])
        else:
            atr, sp, sn = atr - atr / 14 + tr[i], sp - sp / 14 + pdm[i], sn - sn / 14 + ndm[i]
        pdi, ndi = 100 * sp / atr, 100 * sn / atr
        dx = 100 * abs(pdi - ndi) / (pdi + ndi) if pdi + ndi > 0 else 0.0
        adx = dx if adx is None else (adx * 13 + dx) / 14
        if i >= 42:
            out[i]["adx"] = adx
    for i in range(n):
        if "sma50" in out[i]:
            out[i]["dist"] = abs(pc[i] / out[i]["sma50"] - 1.0)
    return out


def side(r, f, k):
    s = f.get(f"sma{k}")
    return None if s is None else (1 if r["pc"] > s else -1)


def coin(d):
    return 1 if hashlib.md5(d.encode()).digest()[0] & 1 else -1


def stats(trades, tp, sp):
    if len(trades) < 5:
        return "        -        "
    w = sum(1 for x in trades if x[0] >= x[1] - 1e-9)
    l = sum(1 for x in trades if x[0] <= -x[2] - 0.2)
    bp = st.mean(x[0] / x.e * 1e4 for x in trades)
    edge = (w / max(1, w + l) - sp / (tp + sp)) * 100
    return f"{edge:+5.1f}pp {bp:+5.1f}bp n{len(trades):4d}"


def main():
    data = sys.argv[1]
    rows = load(data)
    F = features(rows)
    print(f"T931 rows {len(rows)} ({rows[0]['date']} .. {rows[-1]['date']})")
    hdr = " | ".join(f"{e[0]:^22s}" for e in ERAS)
    for tp, sp in ((20, 40), (25, 40)):
        print(f"\n=== A. resolved win minus random {sp / (tp + sp) * 100:.1f}% and mean bp, +{tp / 100:.2f} / -{sp / 100:.2f}")
        print(f"{'bias':<12s} {hdr}")
        rules = [(f"SMA{k}", lambda r, f, k=k: side(r, f, k)) for k in (5, 10, 20, 50, 100, 200)]
        rules += [("always long", lambda r, f: 1), ("coin flip", lambda r, f: coin(r["date"]))]
        for name, fn in rules:
            cells = []
            for _, lo, hi in ERAS:
                tr = [W.trade_pts(r, s, CL, tp, sp) for r, f in zip(rows, F) if lo <= r["date"] < hi and "sma200" in f
                      for s in [fn(r, f)] if s]
                cells.append(f"{stats(tr, tp, sp):^22s}")
            print(f"{name:<12s} " + " | ".join(cells))

    print("\n=== A2. evaluation 50K (INTRA, NQ 28,530, +0.20/-0.40): days to a pass | evaluations | fees")
    for _, lo, hi in ERAS[:4]:
        cal = [r["date"] for r in rows if lo <= r["date"] < hi]
        cells = []
        for name, fn in (("SMA50", lambda r, f: side(r, f, 50)), ("long", lambda r, f: 1), ("coin", lambda r, f: coin(r["date"]))):
            sig = {}
            for r, f in zip(rows, F):
                if lo <= r["date"] < hi:
                    s = fn(r, f)
                    if s:
                        sig[r["date"]] = E.scaled(r, s, 20, 40)
            # eval_25k.scaled uses the multi-feature levels; T931 uses CL - same grid
            dd, ev, p = E.run(sig, cal, E.ACC["50K"])
            cells.append(f"{name} {dd:5.1f} d {ev:4.2f} ev ${ev * 90:4.0f}")
        print(f"   {lo}-{int(hi) - 1}: " + "   ".join(cells))

    print("\n=== B. SMA50 sprint (+0.20/-0.40) by daily regime before the day")
    print(f"{'regime':<16s} {hdr}")
    splits = (("ER20 chop <.20", lambda f: f.get("er20") is not None and f["er20"] < 0.20),
              ("ER20 mid", lambda f: f.get("er20") is not None and 0.20 <= f["er20"] < 0.35),
              ("ER20 trend", lambda f: f.get("er20") is not None and f["er20"] >= 0.35),
              ("ADX chop <20", lambda f: f.get("adx") is not None and f["adx"] < 20),
              ("ADX mid", lambda f: f.get("adx") is not None and 20 <= f["adx"] < 25),
              ("ADX trend >=25", lambda f: f.get("adx") is not None and f["adx"] >= 25),
              ("DIST near <1%", lambda f: f.get("dist") is not None and f["dist"] < 0.01),
              ("DIST mid", lambda f: f.get("dist") is not None and 0.01 <= f["dist"] < 0.03),
              ("DIST far >=3%", lambda f: f.get("dist") is not None and f["dist"] >= 0.03))
    for name, keep in splits:
        cells = []
        for _, lo, hi in ERAS:
            tr = [W.trade_pts(r, s, CL, 20, 40) for r, f in zip(rows, F) if lo <= r["date"] < hi and "sma200" in f and keep(f)
                  for s in [side(r, f, 50)] if s]
            cells.append(f"{stats(tr, 20, 40):^22s}")
        print(f"{name:<16s} " + " | ".join(cells))

    print("\n=== C. POST-HOC: faster SMA in chop, SMA50 otherwise (+0.20/-0.40)")
    print(f"{'rule':<20s} {hdr}")
    for cname, chop in (("ER<.20", lambda f: f.get("er20", 1) < 0.20), ("ADX<20", lambda f: f.get("adx", 99) < 20)):
        for k in (5, 10, 20):
            cells = []
            for _, lo, hi in ERAS:
                tr = []
                for r, f in zip(rows, F):
                    if lo <= r["date"] < hi and "sma200" in f:
                        s = side(r, f, k) if chop(f) else side(r, f, 50)
                        tr.append(W.trade_pts(r, s, CL, 20, 40))
                cells.append(f"{stats(tr, 20, 40):^22s}")
            print(f"{cname + ' -> SMA' + str(k):<20s} " + " | ".join(cells))


if __name__ == "__main__":
    main()
