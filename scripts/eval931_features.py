"""09:31 eval sprint (Lucid 7): what else predicts the direction? Broad
feature scan (owner request 2026-11-04: "prior-day delta, premarket, Asia,
London ... these were only examples, use your own ideas and internet
sources"). Rules and pass criteria FIXED BEFORE RESULTS.

Trade: entry at the 09:31 close, bracket +0.20% / -0.40% (Lucid 7), flat
15:55. A rule gives a side (+1 / -1) or no trade (0) from information known at
09:31 only (overnight session, Asia / London, the 09:30 open and first minute,
the prior RTH day, daily history, calendar, other markets' overnight moves).
Metric: resolved win rate (target before stop) minus the random-walk rate
S / (T + S) = 66.7%, by era 2010-13 / 2014-17 / 2018-21 / 2022-25 / 2026;
pooled 2010-25 z = (wins - n p) / sqrt(n p (1 - p)); mean gross bp incl.
unresolved.
Verdict (fixed): CANDIDATE = edge > 0 in all four eras 2010-25 AND pooled
z >= 2 AND 2026 not below -5 pp (or n < 20); STRONG = CANDIDATE with z >= 3
(~60 rules are scanned, so z >= 3 is the multiple-testing bar). A rule that
cannot be computed before 2018 (cross-market) can at most be "info".

Sources for the rule ideas:
  Gao, Han, Li & Zhou (JFE 2018) market intraday momentum - the first
    half-hour return (from the prior close) predicts the last half-hour.
  Yu, Rentzler & Wolf (JOIM) NASDAQ-100 futures: overnight return mostly
    reverses intraday, momentum depends on signs / Mondays.
  Overnight-intraday reversal (Lou, Polk & Skouras; practitioner CO-OC tests).
  Pagonidis (2013) IBS effect; Connors RSI(2); streak reversal.
  Dalton (Mind over Markets): open vs prior value area / POC.
  Gap-fill statistics for ES / NQ (small gaps fill more often).
  NQ Statistical Mapper (TradingView): NY open vs London midpoint -> which
    London extreme is hit first; ICT-style Asia range taken by London.
  Calendar: weekday, turn of month, pre-/post-holiday.
  Owner: prior-day delta (here a bulk-volume-classification proxy on 5-min
    bars; the real aggressor delta needs an in-QC run).
Own ideas: overnight-volume-conditioned gap follow / fade, NR7 + gap, 20-day
breakout, relative overnight strength vs ES / RTY, bonds' overnight move.

Part B: walk-forward combination (no hand-picking): logistic regression and
a shallow gradient-boosting model on all continuous features, label = which
of +0.20% / -0.20% is touched first; trained on 2010-17 -> traded 2018-26, and
trained on 2018-25 -> traded 2010-17; side = sign(p - 0.5) with the real
+0.20 / -0.40 bracket.
Part C: 50K evaluation (INTRA, NQ 28,530) days / fees for any CANDIDATE, the
combination, SMA50 and a coin flip.
Usage: eval931_features.py DATA_DIR
"""
from __future__ import annotations

import datetime as dt
import math
import os
import statistics as st
import sys

import numpy as np

sys.path.insert(0, "scripts")
import eval_25k as E  # noqa: E402
import two_win_sprint as W  # noqa: E402
from score_cond_bracket import parse, LEVELS as CL  # noqa: E402
from eval931_regimes import load, features, side as smaside, coin  # noqa: E402

ERAS = (("2010-13", "2010", "2014"), ("2014-17", "2014", "2018"), ("2018-21", "2018", "2022"),
        ("2022-25", "2022", "2026"), ("2026", "2026", "2027"))
P = 40 / 60
PANELS = ("B2_0A", "B2_0B", "B2A", "B2B", "B2_26")


def panels(data):
    """date -> H fields + RTH 5-min bars (o, h, l, c, v)."""
    out = {}
    raw_b = {}
    for nm in PANELS:
        for line in open(os.path.join(data, f"{nm}_tags.txt")):
            f = line.strip().split(",")
            d = f"{f[1][:4]}-{f[1][4:6]}-{f[1][6:]}" if len(f) > 1 else ""
            if f[0] == "H" and len(f) >= 16:
                out[d] = {"exp": f[2], "onh": float(f[3]), "onl": float(f[4]), "onpoc": float(f[5]),
                          "onvol": float(f[6]), "poc": float(f[7]), "vah": float(f[8]), "val": float(f[9]),
                          "vol": float(f[10]), "base": float(f[11]), "ah": float(f[12]), "al": float(f[13]),
                          "lh": float(f[14]), "ll": float(f[15])}
                raw_b[d] = {}
            elif f[0] == "B" and len(f) >= 4 and d in raw_b:
                raw_b[d][int(f[2])] = f[3]
    for d, h in out.items():
        b = []
        for k in sorted(raw_b[d]):
            for s in raw_b[d][k].split("/"):
                o, hi, lo, c, v = (int(x) for x in s.split(":"))
                b.append((h["base"] + o / 4, h["base"] + hi / 4, h["base"] + lo / 4, h["base"] + c / 4, v))
        h["bars"] = b if len(b) >= 78 else None          # half days: no prior-day bar features
    return out


def xmkt(data):
    """sym -> date -> overnight gap (09:30 open / prior close - 1), 2018-25."""
    out = {}
    for sym in ("ES", "RTY", "ZN", "GC", "CL", "YM"):
        m = {}
        p = os.path.join(data, f"XM_{sym}_tags.txt")
        if os.path.exists(p):
            for r in parse([p]):
                if r["pc"] > 0:
                    m[r["date"]] = r["o930"] / r["pc"] - 1.0
        out[sym] = m
    return out


def sgn(x, eps=0.0):
    return 1 if x > eps else (-1 if x < -eps else 0)


def rsi2(closes):
    """Wilder RSI(2) series over the list of closes."""
    out = [None] * len(closes)
    ag = al = None
    for i in range(1, len(closes)):
        ch = closes[i] - closes[i - 1]
        g, l = max(ch, 0.0), max(-ch, 0.0)
        if i < 2:
            ag, al = g, l
            continue
        ag, al = (ag + g) / 2.0, (al + l) / 2.0
        out[i] = 100.0 if al == 0 else 100.0 - 100.0 / (1.0 + ag / al)
    return out


def build(rows, pan, xm):
    """Context per row (all known at 09:31)."""
    F = features(rows)
    pc = [r["pc"] for r in rows]
    rs = rsi2(pc)
    dates = [r["date"] for r in rows]
    onv = []
    ctx = []
    for i, r in enumerate(rows):
        d = r["date"]
        c = {"date": d, "sma": smaside(r, F[i], 50), "er20": F[i].get("er20"), "adx": F[i].get("adx")}
        c["gap"] = r["o930"] / r["pc"] - 1.0
        c["m1"] = r["e"] / r["o930"] - 1.0
        c["pret"] = pc[i] / pc[i - 1] - 1.0 if i >= 1 else None
        c["wret"] = pc[i] / pc[i - 5] - 1.0 if i >= 5 else None
        c["rsi2"] = rs[i]
        k = 0
        while i - k - 1 >= 0 and pc[i - k] < pc[i - k - 1]:
            k += 1
        u = 0
        while i - u - 1 >= 0 and pc[i - u] > pc[i - u - 1]:
            u += 1
        c["streak"] = -k if k else u
        if i >= 20:
            w = pc[i - 19:i + 1]
            c["hi20"] = (pc[i] - min(w)) / (max(w) - min(w)) if max(w) > min(w) else 0.5
        c["pdhl"] = 1 if r["o930"] > r["pdh"] else (-1 if r["o930"] < r["pdl"] else 0)
        h = pan.get(d)
        if h:
            rng = h["onh"] - h["onl"]
            c["onpos"] = (r["e"] - h["onl"]) / rng if rng > 0 else 0.5
            c["onbrk"] = 1 if r["e"] > h["onh"] else (-1 if r["e"] < h["onl"] else 0)
            c["onpoc"] = sgn(r["e"] - h["onpoc"])
            onv.append(h["onvol"])
            if len(onv) > 60:
                c["onr"] = h["onvol"] / st.median(onv[-61:-1])
            if h["ah"] > 0 and h["lh"] > 0:
                up, dn = h["lh"] > h["ah"], h["ll"] < h["al"]
                c["ldn"] = 1 if (up and not dn) else (-1 if (dn and not up) else 0)
                c["lmid"] = sgn(r["e"] - (h["lh"] + h["ll"]) / 2.0)
                c["asia"] = 1 if r["e"] > h["ah"] else (-1 if r["e"] < h["al"] else 0)
            c["onrng"] = rng / r["e"]
        pd = pan.get(dates[i - 1]) if i >= 1 else None
        if pd and pd.get("bars") and h:
            b = pd["bars"][:78]
            H, L, C = max(x[1] for x in b), min(x[2] for x in b), b[-1][3]
            c["ibs"] = (C - L) / (H - L) if H > L else 0.5
            c["lh"] = C / b[65][3] - 1.0
            tv = sum(x[4] for x in b)
            if tv > 0:
                c["pvwap"] = C / (sum((x[1] + x[2] + x[3]) / 3 * x[4] for x in b) / tv) - 1.0
            bvc = lambda xs: sum(x[4] * ((2 * (x[3] - x[2]) / (x[1] - x[2]) - 1) if x[1] > x[2] else 0) for x in xs) / max(1, sum(x[4] for x in xs))
            c["delta"] = bvc(b)
            c["lhdelta"] = bvc(b[66:])
            c["prng"] = (H - L) / C
            if pd["exp"] == h["exp"]:               # same contract: compare today's open with yesterday's profile
                o = r["o930"]
                c["va"] = 1 if o > pd["vah"] else (-1 if o < pd["val"] else 0)
                c["ppoc"] = sgn(o - pd["poc"])
            c["pvol"] = pd["vol"]
        ctx.append(c)
    # rolling items needing history of ctx
    for i, c in enumerate(ctx):
        pr = [ctx[j].get("prng") for j in range(max(0, i - 6), i + 1)]
        if len(pr) == 7 and None not in pr:
            c["nr7"] = pr[-1] <= min(pr)
        pv = [ctx[j].get("pvol") for j in range(max(0, i - 20), i)]
        if len(pv) == 20 and None not in pv and c.get("pvol"):
            c["pvolr"] = c["pvol"] / st.mean(pv)
        d = dt.date.fromisoformat(c["date"])
        c["dow"] = d.weekday()
        nxt = dt.date.fromisoformat(ctx[i + 1]["date"]) if i + 1 < len(ctx) else None
        prv = dt.date.fromisoformat(ctx[i - 1]["date"]) if i >= 1 else None
        bd = lambda a, b_: int(np.busday_count(a, b_))
        c["prehol"] = nxt is not None and bd(d, nxt) > 1
        c["posthol"] = prv is not None and bd(prv, d) > 1
        last_of_month = nxt is not None and nxt.month != d.month
        first_n = sum(1 for j in range(max(0, i - 3), i + 1) if dt.date.fromisoformat(ctx[j]["date"]).month == d.month)
        c["tom"] = last_of_month or (prv is not None and first_n <= 3 and
                                     dt.date.fromisoformat(ctx[i - first_n]["date"]).month != d.month)
        for sym, m in xm.items():
            if c["date"] in m:
                c["x" + sym] = m[c["date"]]
    return ctx


def g(c, k):
    return c.get(k)


RULES = [
    # --- overnight / premarket / sessions
    ("GAP follow", "ON", lambda c: sgn(c["gap"], 0.0005)),
    ("GAP fade", "ON", lambda c: -sgn(c["gap"], 0.0005)),
    ("GAP >=0.5% follow", "ON", lambda c: sgn(c["gap"]) if abs(c["gap"]) >= 0.005 else 0),
    ("GAP 0.05-0.25% fade", "ON", lambda c: -sgn(c["gap"]) if 0.0005 <= abs(c["gap"]) < 0.0025 else 0),
    ("1st minute follow", "ON", lambda c: sgn(c["m1"], 0.0002)),
    ("1st minute fade", "ON", lambda c: -sgn(c["m1"], 0.0002)),
    ("gap+1st min agree", "ON", lambda c: sgn(c["gap"], 0.0005) if sgn(c["gap"], 0.0005) == sgn(c["m1"], 0.0002) else 0),
    ("ON range pos >.5", "ON", lambda c: (1 if c["onpos"] > 0.5 else -1) if g(c, "onpos") is not None else 0),
    ("ON range extremes fade", "ON", lambda c: (-1 if c["onpos"] > 0.9 else (1 if c["onpos"] < 0.1 else 0)) if g(c, "onpos") is not None else 0),
    ("ON high/low break follow", "ON", lambda c: g(c, "onbrk") or 0),
    ("ON high/low break fade", "ON", lambda c: -(g(c, "onbrk") or 0)),
    ("vs ON POC follow", "ON", lambda c: g(c, "onpoc") or 0),
    ("London took Asia side follow", "ON", lambda c: g(c, "ldn") or 0),
    ("London took Asia side fade", "ON", lambda c: -(g(c, "ldn") or 0)),
    ("vs London mid follow", "ON", lambda c: g(c, "lmid") or 0),
    ("vs London mid fade", "ON", lambda c: -(g(c, "lmid") or 0)),
    ("outside Asia range follow", "ON", lambda c: g(c, "asia") or 0),
    ("outside Asia range fade", "ON", lambda c: -(g(c, "asia") or 0)),
    ("high ON vol: gap follow", "ON", lambda c: sgn(c["gap"], 0.0005) if (g(c, "onr") or 0) > 1.2 else 0),
    ("low ON vol: gap fade", "ON", lambda c: -sgn(c["gap"], 0.0005) if 0 < (g(c, "onr") or 0) < 0.8 else 0),
    ("narrow ON range: gap follow", "ON", lambda c: sgn(c["gap"], 0.0005) if (g(c, "onrng") or 1) < 0.004 else 0),
    # --- prior day
    ("prior day ret follow", "PD", lambda c: sgn(c["pret"]) if g(c, "pret") is not None else 0),
    ("prior day ret fade", "PD", lambda c: -sgn(c["pret"]) if g(c, "pret") is not None else 0),
    ("IBS <.2 long / >.8 short", "PD", lambda c: (1 if c["ibs"] < 0.2 else (-1 if c["ibs"] > 0.8 else 0)) if g(c, "ibs") is not None else 0),
    ("IBS follow (>.5 long)", "PD", lambda c: (1 if c["ibs"] > 0.5 else -1) if g(c, "ibs") is not None else 0),
    ("prior last hour follow", "PD", lambda c: sgn(c["lh"]) if g(c, "lh") is not None else 0),
    ("prior last hour fade", "PD", lambda c: -sgn(c["lh"]) if g(c, "lh") is not None else 0),
    ("prior close vs VWAP follow", "PD", lambda c: sgn(c["pvwap"]) if g(c, "pvwap") is not None else 0),
    ("prior close vs VWAP fade", "PD", lambda c: -sgn(c["pvwap"]) if g(c, "pvwap") is not None else 0),
    ("prior delta(BVC) follow", "PD", lambda c: sgn(c["delta"], 0.02) if g(c, "delta") is not None else 0),
    ("prior delta(BVC) fade", "PD", lambda c: -sgn(c["delta"], 0.02) if g(c, "delta") is not None else 0),
    ("last-hour delta follow", "PD", lambda c: sgn(c["lhdelta"], 0.05) if g(c, "lhdelta") is not None else 0),
    ("last-hour delta fade", "PD", lambda c: -sgn(c["lhdelta"], 0.05) if g(c, "lhdelta") is not None else 0),
    ("open vs prior VA follow", "PD", lambda c: g(c, "va") or 0),
    ("open vs prior VA fade", "PD", lambda c: -(g(c, "va") or 0)),
    ("open vs prior POC follow", "PD", lambda c: g(c, "ppoc") or 0),
    ("open beyond PDH/PDL follow", "PD", lambda c: c["pdhl"]),
    ("open beyond PDH/PDL fade", "PD", lambda c: -c["pdhl"]),
    ("NR7: gap follow", "PD", lambda c: sgn(c["gap"], 0.0005) if g(c, "nr7") else 0),
    ("big prior vol: ret follow", "PD", lambda c: sgn(c["pret"]) if (g(c, "pvolr") or 0) > 1.5 and g(c, "pret") is not None else 0),
    # --- daily history
    ("RSI2 <10 long / >90 short", "DH", lambda c: (1 if c["rsi2"] < 10 else (-1 if c["rsi2"] > 90 else 0)) if g(c, "rsi2") is not None else 0),
    ("3+ day streak fade", "DH", lambda c: 1 if c["streak"] <= -3 else (-1 if c["streak"] >= 3 else 0)),
    ("3+ day streak follow", "DH", lambda c: -1 if c["streak"] <= -3 else (1 if c["streak"] >= 3 else 0)),
    ("5-day ret follow", "DH", lambda c: sgn(c["wret"]) if g(c, "wret") is not None else 0),
    ("5-day ret fade", "DH", lambda c: -sgn(c["wret"]) if g(c, "wret") is not None else 0),
    ("20-day high/low follow", "DH", lambda c: (1 if c["hi20"] >= 1 else (-1 if c["hi20"] <= 0 else 0)) if g(c, "hi20") is not None else 0),
    ("SMA50 (Lucid 7)", "DH", lambda c: c["sma"] or 0),
    ("SMA50 + gap agree", "DH", lambda c: (c["sma"] or 0) if (c["sma"] or 0) == sgn(c["gap"], 0.0005) else 0),
    ("SMA50 + prior VA agree", "DH", lambda c: (c["sma"] or 0) if (c["sma"] or 0) == (g(c, "va") or 0) else 0),
    # --- calendar (always long on the subset)
    ("always long", "CAL", lambda c: 1),
    ("Monday long", "CAL", lambda c: 1 if c["dow"] == 0 else 0),
    ("Tuesday long", "CAL", lambda c: 1 if c["dow"] == 1 else 0),
    ("Wednesday long", "CAL", lambda c: 1 if c["dow"] == 2 else 0),
    ("Thursday long", "CAL", lambda c: 1 if c["dow"] == 3 else 0),
    ("Friday long", "CAL", lambda c: 1 if c["dow"] == 4 else 0),
    ("turn of month long", "CAL", lambda c: 1 if c["tom"] else 0),
    ("pre-holiday long", "CAL", lambda c: 1 if c["prehol"] else 0),
    ("post-holiday long", "CAL", lambda c: 1 if c["posthol"] else 0),
    ("coin flip", "CAL", lambda c: coin(c["date"])),
    # --- other markets' overnight move (2018-25 only)
    ("NQ stronger than ES ON", "XM", lambda c: sgn(c["gap"] - c["xES"], 0.0005) if "xES" in c else 0),
    ("NQ stronger than RTY ON", "XM", lambda c: sgn(c["gap"] - c["xRTY"], 0.001) if "xRTY" in c else 0),
    ("bonds (ZN) ON follow", "XM", lambda c: sgn(c["xZN"], 0.0005) if "xZN" in c else 0),
    ("gold ON follow", "XM", lambda c: sgn(c["xGC"], 0.001) if "xGC" in c else 0),
    ("crude ON follow", "XM", lambda c: sgn(c["xCL"], 0.002) if "xCL" in c else 0),
]


def era_of(d):
    for k, (_, lo, hi) in enumerate(ERAS):
        if lo <= d < hi:
            return k
    return None


def score(trades):
    """trades = list of TP; -> (edge pp, wins, resolved, mean bp, n)."""
    w = sum(1 for x in trades if x[0] >= x[1] - 1e-9)
    l = sum(1 for x in trades if x[0] <= -x[2] - 0.2)
    n = len(trades)
    bp = st.mean(x[0] / x.e * 1e4 for x in trades) if n else 0.0
    edge = (w / (w + l) - P) * 100 if w + l else 0.0
    return edge, w, w + l, bp, n


def cell(s):
    edge, w, res, bp, n = s
    return f"{edge:+5.1f}pp {bp:+5.1f}bp n{n:4d}" if n >= 15 else f"{'-':^22s}"


def scan(rows, ctx, sidefn):
    per = [[] for _ in ERAS]
    for r, c in zip(rows, ctx):
        k = era_of(r["date"])
        if k is None or c.get("adx") is None:
            continue
        s = sidefn(c)
        if s:
            per[k].append(W.trade_pts(r, s, CL, 20, 40))
    sc = [score(t) for t in per]
    w = sum(s[1] for s in sc[:4])
    res = sum(s[2] for s in sc[:4])
    z = (w - res * P) / math.sqrt(res * P * (1 - P)) if res else 0.0
    return sc, z


def verdict(sc, z, grp):
    four = all(s[4] >= 15 and s[0] > 0 for s in sc[:4])
    ok26 = sc[4][4] < 20 or sc[4][0] > -5.0
    if grp == "XM":
        return "info" if (sc[2][0] > 0 and sc[3][0] > 0 and z >= 2) else "-"
    if four and z >= 3 and ok26:
        return "STRONG"
    if four and z >= 2 and ok26:
        return "CANDIDATE"
    return "-"


FEATS = ["gap", "m1", "onpos", "onbrk", "onpoc", "ldn", "lmid", "asia", "onr", "onrng", "pret", "wret", "rsi2",
         "streak", "hi20", "pdhl", "ibs", "lh", "pvwap", "delta", "lhdelta", "prng", "va", "ppoc", "pvolr",
         "sma", "er20", "adx", "dow", "tom", "prehol", "posthol"]


def label(r):
    """+1 if +0.20% is touched before -0.20%, -1 if the reverse, 0 if neither."""
    k = CL.index(20)
    u, d = r["up"][k], r["dn"][k]
    if u >= 0 and (d < 0 or u < d):
        return 1
    if d >= 0 and (u < 0 or d < u):
        return -1
    return 0


def matrix(ctx, idx):
    X = []
    for i in idx:
        c = ctx[i]
        row = []
        for f in FEATS:
            v = c.get(f)
            v = 0.0 if v is None else float(v)
            row.append(v)
        row += [1.0 if c["dow"] == k else 0.0 for k in range(5)]
        X.append(row)
    return np.array(X)


def combo(rows, ctx):
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    ok = [i for i, c in enumerate(ctx) if c.get("adx") is not None and c.get("onr") is not None]
    out = {}
    splits = (("train 2010-17", lambda d: d < "2018", lambda d: d >= "2018"),
              ("train 2018-25", lambda d: "2018" <= d < "2026", lambda d: d < "2018" or d >= "2026"))
    for sname, tr, te in splits:
        itr = [i for i in ok if tr(rows[i]["date"]) and label(rows[i]) != 0]
        ite = [i for i in ok if te(rows[i]["date"])]
        y = np.array([label(rows[i]) for i in itr])
        for mname, model in (("logit", make_pipeline(StandardScaler(), LogisticRegression(C=0.1, max_iter=2000))),
                             ("gbm", HistGradientBoostingClassifier(max_depth=2, max_iter=150, learning_rate=0.05,
                                                                   min_samples_leaf=80, random_state=1))):
            model.fit(matrix(ctx, itr), y)
            p = model.predict_proba(matrix(ctx, ite))[:, list(model.classes_).index(1)]
            out[(sname, mname)] = {rows[i]["date"]: (1 if q > 0.5 else -1) for i, q in zip(ite, p)}
            ptr = model.predict_proba(matrix(ctx, itr))[:, list(model.classes_).index(1)]
            acc = np.mean((ptr > 0.5) == (y == 1)) * 100
            out[(sname, mname, "acc")] = acc
    return out


def main():
    data = sys.argv[1]
    rows = load(data)
    pan = panels(data)
    xm = xmkt(data)
    ctx = build(rows, pan, xm)
    print(f"T931 rows {len(rows)} ({rows[0]['date']} .. {rows[-1]['date']}), panel days {len(pan)}")
    hdr = " | ".join(f"{e[0]:^22s}" for e in ERAS)
    print(f"\n=== A. single rules, +0.20 / -0.40, resolved win minus random 66.7% | mean bp | n; z = pooled 2010-25")
    print(f"{'rule':<30s} {hdr} |   z   verdict")
    cand = []
    for name, grp, fn in RULES:
        sc, z = scan(rows, ctx, fn)
        v = verdict(sc, z, grp)
        if v in ("STRONG", "CANDIDATE"):
            cand.append((name, fn))
        print(f"{name:<30s} " + " | ".join(f"{cell(s):^22s}" for s in sc) + f" | {z:+5.1f} {v}")
    import hashlib
    nul = 0
    for k in range(300):                       # empirical null: random sides, same days
        fn = lambda c, k=k: 1 if hashlib.md5(f"{k}{c['date']}".encode()).digest()[0] & 1 else -1
        sc, z = scan(rows, ctx, fn)
        nul += verdict(sc, z, "N") in ("STRONG", "CANDIDATE")
    print(f"\nnull check: {nul} of 300 coin-flip rules reach CANDIDATE -> expect ~{nul / 300 * len(RULES):.1f} false candidates among {len(RULES)} rules")

    print("\n=== B. walk-forward combination (all features, label = +0.20 vs -0.20 first), traded +0.20 / -0.40")
    cb = combo(rows, ctx)
    for key, sig in cb.items():
        if len(key) == 3:
            continue
        sc, z = scan(rows, ctx, lambda c, sig=sig: sig.get(c["date"], 0))
        print(f"{key[0]} {key[1]:<6s} (in-sample acc {cb[key + ('acc',)]:4.1f}%) " + " | ".join(f"{cell(s):^22s}" for s in sc))

    print("\n=== C. 50K evaluation (INTRA, NQ 28,530, +0.20/-0.40): days to a pass | evaluations | fees")
    tests = [("SMA50", lambda c: c["sma"] or 0), ("coin", lambda c: coin(c["date"]))] + cand
    tests += [(f"{k[1]} {k[0][6:]}", (lambda c, s=v: s.get(c["date"], 0))) for k, v in cb.items() if len(k) == 2]
    by = {r["date"]: (r, c) for r, c in zip(rows, ctx)}
    for _, lo, hi in ERAS[:4]:
        cal = [r["date"] for r in rows if lo <= r["date"] < hi]
        cells = []
        for name, fn in tests:
            sig = {}
            for d in cal:
                r, c = by[d]
                s = fn(c)
                if s:
                    sig[d] = E.scaled(r, s, 20, 40)
            if len(sig) < 100:
                continue
            dd, ev, _ = E.run(sig, cal, E.ACC["50K"])
            cells.append(f"{name} {dd:4.1f}d ${ev * 90:3.0f}")
        print(f"   {lo}-{int(hi) - 1}: " + " | ".join(cells))


if __name__ == "__main__":
    main()
