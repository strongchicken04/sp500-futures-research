"""Eval sprint AFTER the open: enter at 10:00 (and 10:30 / 11:00) in the
direction chosen by the first 30 / 60 / 90 minutes (owner request 2026-11-05:
"long / short at 10:00 by the close of the first 30-min candle - bullish /
bearish, above / below EMA, SMA, VWAP ... does the noise of the big opening
volume disappear after the first hour and the market pick a side? mean
reversion is fine too"). Rules and pass criteria FIXED BEFORE RESULTS.

Trade: entry at the close of the decision bar (10:00 / 10:30 / 11:00, CBA
T1000 / T1030 / T1100 rows = minute data, first touch to 15:55), bracket
+0.20% / -0.30% (RS sprint plan; random-walk resolved win 60%) and +0.20% /
-0.40% (Lucid 7 shape; 66.7%). Features from the 5-min RTH bars up to the
decision bar (exactly the entry price), the daily history, VIX (MFEAT, 10:00
and 11:00 only) and the RS benchmark (NQ - ES since the open > 0.15% and
above VWAP = Lucid 8 at its first check).
Each idea is scored as FOLLOW (momentum: the side the opening picked) and as
FADE (mean reversion), from the window open (09:30) to the decision bar:
  color (|ret| >= 0.05%), |ret| >= 0.15 / 0.30 / 0.50%, close vs VWAP, vs EMA20 /
  EMA50 / SMA20 of 5-min closes, close location in the window range (CLV >0.7 /
  <0.3), close vs prior close, beyond the overnight high / low, beyond the prior
  day high / low, strong body (> 60% of the range), high / low window volume
  (vs the same window over 20 days), narrow / wide window range, opening drive,
  first 5 min vs the window disagree (the later move wins?), color + VWAP agree,
  color + daily SMA50 agree, color + VWAP + EMA20 agree, gap-and-go / gap filled,
  VWAP stretch > 0.30% (reversion), high VIX (vixrel > 1.1) and low VIX
  (< 0.9) with the color, always long, coin flip, RS (benchmark).
Metric and verdict as eval931_features.py: resolved win minus random by era
(2010-13 / 2014-17 / 2018-21 / 2022-25 / 2026), pooled 2010-25 z; CANDIDATE =
all four eras > 0, z >= 2, 2026 not below -5 pp (or n < 20); STRONG = z >= 3;
empirical null from 300 coin-flip rules per entry time. Part B: 50K evaluation
(INTRA, NQ 28,530, +0.20 / -0.30) for the candidates vs the RS sprint (all four
checks, the live rule) and a coin flip.
Usage: sprint_post_open.py DATA_DIR
"""
from __future__ import annotations

import hashlib
import math
import statistics as st
import sys

sys.path.insert(0, "scripts")
import eval_25k as E  # noqa: E402
import two_win_sprint as W  # noqa: E402
from eval931_features import panels, sgn, ERAS, era_of  # noqa: E402
from eval931_regimes import features as dfeat  # noqa: E402
from score_cond_bracket import parse, LEVELS as CL  # noqa: E402
from score_multi_feature import parse as parse_mf, first_signals  # noqa: E402

TIMES = (("10:00", "T1000", 5, 600), ("10:30", "T1030", 11, None), ("11:00", "T1100", 17, 660))
BR = ((20, 30), (20, 40))


def load(data, typ):
    rows = {}
    for f in ("CBA_OLD", "CBA26", "CBA"):
        for r in parse([f"{data}/{f}_tags.txt"]):
            if r["type"] == typ:
                rows[r["date"]] = r
    return [rows[d] for d in sorted(rows)]


def mfeat(data):
    out = {}
    for f in ("MFEAT_OLD", "MFEAT", "MFEAT26"):
        for r in parse_mf(f"{data}/{f}_tags.txt"):
            out[(r["date"], r["hm"])] = r
    return out


def emas(pan):
    """(date, bar) -> (ema20, ema50, sma20) of continuous 5-min RTH closes (value at that bar)."""
    out = {}
    e20 = e50 = None
    win = []
    for d in sorted(pan):
        b = pan[d].get("bars")
        if not b:
            continue
        for k, x in enumerate(b[:78]):
            c = x[3]
            e20 = c if e20 is None else e20 + (c - e20) * 2 / 21
            e50 = c if e50 is None else e50 + (c - e50) * 2 / 51
            win.append(c)
            if len(win) > 20:
                win.pop(0)
            if k in (5, 11, 17):
                out[(d, k)] = (e20, e50, sum(win) / len(win))
    return out


def build(rows, pan, em, mf, k, hm):
    F = dfeat(rows)
    dates = [r["date"] for r in rows]
    wv, wr = [], []
    ctx = []
    for i, r in enumerate(rows):
        d = r["date"]
        h = pan.get(d)
        c = {"date": d}
        if not h or not h.get("bars") or (d, k) not in em:
            ctx.append(c)
            continue
        b = h["bars"][:k + 1]
        o, cl = b[0][0], b[k][3]
        H, L = max(x[1] for x in b), min(x[2] for x in b)
        V = sum(x[4] for x in b)
        tv = V if V > 0 else 1
        vwap = sum((x[1] + x[2] + x[3]) / 3 * x[4] for x in b) / tv if V > 0 else cl
        c.update({"ret": cl / o - 1, "day": cl / r["pc"] - 1, "gap": o / r["pc"] - 1,
                  "vw": cl / vwap - 1, "clv": (cl - L) / (H - L) if H > L else 0.5,
                  "body": abs(cl - o) / (H - L) if H > L else 0.0, "rng": (H - L) / cl,
                  "f5": b[0][3] / o - 1, "onh": cl > r["onh"], "onl": cl < r["onl"],
                  "pdh": cl > r["pdh"], "pdl": cl < r["pdl"],
                  "drive": 1 if (L >= o * (1 - 0.0005) and cl >= o * 1.0015) else (-1 if (H <= o * 1.0005 and cl <= o * 0.9985) else 0)})
        e20, e50, s20 = em[(d, k)]
        c.update({"e20": cl / e20 - 1, "e50": cl / e50 - 1, "s20": cl / s20 - 1})
        c["sma"] = 0 if F[i].get("sma50") is None else (1 if r["pc"] > F[i]["sma50"] else -1)
        if len(wv) >= 20:
            c["volr"] = V / (sum(wv[-20:]) / 20) if sum(wv[-20:]) > 0 else None
            c["rngr"] = c["rng"] / st.median(wr[-20:])
        wv.append(V)
        wr.append(c["rng"])
        if hm is not None and (d, hm) in mf:
            m = mf[(d, hm)]
            c["vixrel"] = m["vixrel"]
            c["rs"] = 1 if (m["rs"] > 0.0015 and m["vwapd"] > 0) else (-1 if (m["rs"] < -0.0015 and m["vwapd"] < 0) else 0)
        c["ok"] = F[i].get("adx") is not None
        ctx.append(c)
    return ctx


def col(c):
    return sgn(c["ret"], 0.0005)


def pair(name, fn):
    return [(name + " FOLLOW", fn), (name + " FADE", lambda c, fn=fn: -fn(c))]


IDEAS = [
    ("30m color", col),
    ("|ret|>=0.15%", lambda c: sgn(c["ret"]) if abs(c["ret"]) >= 0.0015 else 0),
    ("|ret|>=0.30%", lambda c: sgn(c["ret"]) if abs(c["ret"]) >= 0.003 else 0),
    ("|ret|>=0.50%", lambda c: sgn(c["ret"]) if abs(c["ret"]) >= 0.005 else 0),
    ("vs VWAP", lambda c: sgn(c["vw"], 0.0005)),
    ("vs EMA20 5m", lambda c: sgn(c["e20"], 0.0003)),
    ("vs EMA50 5m", lambda c: sgn(c["e50"], 0.0003)),
    ("vs SMA20 5m", lambda c: sgn(c["s20"], 0.0003)),
    ("CLV >.7/<.3", lambda c: 1 if c["clv"] > 0.7 else (-1 if c["clv"] < 0.3 else 0)),
    ("vs prior close", lambda c: sgn(c["day"], 0.0005)),
    ("beyond ON hi/lo", lambda c: 1 if c["onh"] else (-1 if c["onl"] else 0)),
    ("beyond PDH/PDL", lambda c: 1 if c["pdh"] else (-1 if c["pdl"] else 0)),
    ("strong body", lambda c: col(c) if c["body"] > 0.6 else 0),
    ("high volume", lambda c: col(c) if (c.get("volr") or 0) > 1.3 else 0),
    ("low volume", lambda c: col(c) if 0 < (c.get("volr") or 0) < 0.8 else 0),
    ("narrow range", lambda c: col(c) if 0 < (c.get("rngr") or 0) < 0.7 else 0),
    ("wide range", lambda c: col(c) if (c.get("rngr") or 0) > 1.5 else 0),
    ("opening drive", lambda c: c["drive"]),
    ("5m vs window disagree", lambda c: col(c) if sgn(c["f5"], 0.0003) == -col(c) != 0 else 0),
    ("color+VWAP", lambda c: col(c) if col(c) == sgn(c["vw"], 0.0005) else 0),
    ("color+SMA50 daily", lambda c: col(c) if col(c) == c["sma"] else 0),
    ("color+VWAP+EMA20", lambda c: col(c) if col(c) == sgn(c["vw"], 0.0005) == sgn(c["e20"], 0.0003) else 0),
    ("gap-and-go", lambda c: col(c) if abs(c["gap"]) >= 0.0025 and sgn(c["gap"]) == col(c) else 0),
    ("gap filled", lambda c: -sgn(c["gap"]) if abs(c["gap"]) >= 0.0025 and sgn(c["day"]) == -sgn(c["gap"]) else 0),
    ("VWAP stretch >.30%", lambda c: sgn(c["vw"]) if abs(c["vw"]) >= 0.003 else 0),
    ("high VIX", lambda c: col(c) if (c.get("vixrel") or 0) > 1.1 else 0),
    ("low VIX", lambda c: col(c) if 0 < (c.get("vixrel") or 0) < 0.9 else 0),
]
RULES = [x for n, f in IDEAS for x in pair(n, f)]
RULES += [("always long", lambda c: 1), ("coin flip", lambda c: 1 if hashlib.md5(c["date"].encode()).digest()[0] & 1 else -1),
          ("RS (Lucid 8) this check", lambda c: c.get("rs") or 0)]


def scan(rows, ctx, fn, tp, sp):
    P = sp / (tp + sp)
    per = [[] for _ in ERAS]
    for r, c in zip(rows, ctx):
        k = era_of(r["date"])
        if k is None or not c.get("ok"):
            continue
        try:
            s = fn(c)
        except (KeyError, TypeError):
            s = 0
        if s:
            per[k].append(W.trade_pts(r, s, CL, tp, sp))
    sc = []
    for t in per:
        w = sum(1 for x in t if x[0] >= x[1] - 1e-9)
        l = sum(1 for x in t if x[0] <= -x[2] - 0.2)
        bp = st.mean(x[0] / x.e * 1e4 for x in t) if t else 0.0
        sc.append(((w / (w + l) - P) * 100 if w + l else 0.0, w, w + l, bp, len(t)))
    w = sum(s[1] for s in sc[:4])
    n = sum(s[2] for s in sc[:4])
    z = (w - n * P) / math.sqrt(n * P * (1 - P)) if n else 0.0
    return sc, z


def verdict(sc, z):
    four = all(s[4] >= 15 and s[0] > 0 for s in sc[:4])
    ok26 = sc[4][4] < 20 or sc[4][0] > -5.0
    return "STRONG" if four and z >= 3 and ok26 else ("CANDIDATE" if four and z >= 2 and ok26 else "-")


def cell(s):
    return f"{s[0]:+5.1f}pp {s[3]:+5.1f}bp n{s[4]:4d}" if s[4] >= 15 else f"{'-':^22s}"


def main():
    data = sys.argv[1]
    pan = panels(data)
    em = emas(pan)
    mf = mfeat(data)
    hdr = " | ".join(f"{e[0]:^22s}" for e in ERAS)
    cands = []
    keep = {}
    for lab, typ, k, hm in TIMES:
        rows = load(data, typ)
        ctx = build(rows, pan, em, mf, k, hm)
        keep[lab] = (rows, ctx)
        for tp, sp in BR:
            print(f"\n=== entry {lab} (window 09:30-{lab}), bracket +{tp / 100:.2f} / -{sp / 100:.2f}: resolved win minus "
                  f"random {sp / (tp + sp) * 100:.1f}% | mean bp | n; z pooled 2010-25")
            print(f"{'rule':<30s} {hdr} |   z   verdict")
            for name, fn in RULES:
                sc, z = scan(rows, ctx, fn, tp, sp)
                v = verdict(sc, z)
                if v != "-" and (tp, sp) == BR[0]:
                    cands.append((lab, name, fn))
                print(f"{name:<30s} " + " | ".join(f"{cell(s):^22s}" for s in sc) + f" | {z:+5.1f} {v}")
            nul = 0
            for j in range(300):
                sc, z = scan(rows, ctx, lambda c, j=j: 1 if hashlib.md5(f"{j}{c['date']}".encode()).digest()[0] & 1 else -1, tp, sp)
                nul += verdict(sc, z) != "-"
            print(f"null: {nul}/300 coin-flip rules pass -> ~{nul / 300 * len(RULES):.1f} false passes expected among {len(RULES)}")

    print("\n=== B. 50K evaluation (INTRA, NQ 28,530, +0.20/-0.30): days to a pass | fees")
    mfr = {}
    for f in ("MFEAT_OLD", "MFEAT", "MFEAT26"):
        for r in parse_mf(f"{data}/{f}_tags.txt"):
            mfr.setdefault(f, []).append(r)
    rs_all = {}
    for f, rr in mfr.items():
        rs_all.update(first_signals(rr, lambda r: 1 if (r["rs"] > 0.0015 and r["vwapd"] > 0) else
                                    (-1 if (r["rs"] < -0.0015 and r["vwapd"] < 0) else 0)))
    for _, lo, hi in ERAS[:4]:
        rows0, _ = keep["10:00"]
        cal = [r["date"] for r in rows0 if lo <= r["date"] < hi]
        cells = []
        sig = {d: E.scaled(r, s, 20, 30) for d, (r, s) in rs_all.items() if lo <= d < hi}
        dd, ev, _ = E.run(sig, cal, E.ACC["50K"])
        cells.append(f"RS live {dd:4.1f}d ${ev * 90:3.0f}")
        tests = [("10:00", "coin", lambda c: 1 if hashlib.md5(c["date"].encode()).digest()[0] & 1 else -1)] + cands
        for lab, name, fn in tests:
            rows, ctx = keep[lab]
            sig = {}
            for r, c in zip(rows, ctx):
                if lo <= r["date"] < hi and c.get("ok"):
                    try:
                        s = fn(c)
                    except (KeyError, TypeError):
                        s = 0
                    if s:
                        sig[r["date"]] = E.scaled(r, s, 20, 30)
            if len(sig) < 60:
                cells.append(f"{lab} {name}: few")
                continue
            dd, ev, _ = E.run(sig, cal, E.ACC["50K"])
            cells.append(f"{lab} {name} {dd:4.1f}d ${ev * 90:3.0f}")
        print(f"   {lo}-{int(hi) - 1}: " + " | ".join(cells))


if __name__ == "__main__":
    main()
