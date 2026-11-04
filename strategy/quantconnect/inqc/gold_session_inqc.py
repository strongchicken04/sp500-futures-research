# region imports
from AlgorithmImports import *
import math
import numpy as np
# endregion
#
# HOW WELL CAN WE PREDICT GOLD FOR ONE SESSION (ASIA / LONDON / NEW YORK), AND
# HOW OFTEN IS THE DAY STILL BAD? Computed INSIDE QuantConnect (owner request
# 2026-11-05 night; rules fixed before results). Exports no market data: only
# aggregate statistics as runtime statistics.
#
# Sessions (ET, hourly bars, entry at the open of the first bar):
#   A = Asia 18:00-02:00, L = London 02:00-08:00, N = New York 08:00-16:00.
#   v2 (v1 used HOUR bars: QC hourly futures data has no overnight bars and
#   fill-forward repeated the last day bar -> Asia / London were fake): MINUTE
#   bars, fill-forward off, sessions built from minute bars (end times).
#   Session return r = last close / first open - 1 (gold front contract,
#   back-adjusted continuous prices); MAE from the session high / low.
# Features known at the session start (ideas from the literature / practice):
#   gold's last three session returns (p1 p2 p3 - Asia-up / West-down lore,
#   session momentum / reversal), same session over the last 5 days, 1 / 5 /
#   20-day returns, distance from the 50-day SMA (daily close = NY close),
#   20-day volatility, volatility shock |p1| / 60-session mean, previous
#   session range; cross-asset moves in the previous session and the last 24h
#   (silver, S&P, 10y note, euro = inverse dollar, yen, crude; gold - silver);
#   weekday, turn of month, NFP Friday (first Friday).
# Models, per session, walk-forward by year (train on all earlier years, test
#   2013..2026): SEAS = sign of the training mean (seasonality only); RIDGE =
#   ridge regression on standardised features (alpha chosen on the last two
#   training years); GBM = shallow gradient boosting (if sklearn exists);
#   AGREE = trade only when RIDGE and GBM agree. LONG = always long (control).
#   Volatility model: ridge on |r| -> how well "bad days" can be seen ahead.
# Metrics (out of sample 2013+): hit rate of the side, mean bp and t, corr of
#   prediction vs return; the 20% most confident predictions; bad days of the
#   trade that follows the prediction: loss worse than -0.5% / -1%, adverse
#   excursion worse than -1%, worst session (1% of gold ~ $40 at $4,000 =
#   $400 per MGC); by era 2013-17 / 2018-21 / 2022-26. Univariate: the
#   features with the largest |corr| with r and their sign in three eras.

START = (2010, 1, 1)
END = (2026, 12, 31)
TEST0 = 2013
ASSETS = (("GC", "Metals", "GOLD"), ("SI", "Metals", "SILVER"), ("ES", "Indices", "SP_500_E_MINI"),
          ("ZN", "Financials", "Y_10_TREASURY_NOTE"), ("EU", "Currencies", "EUR"),
          ("JY", "Currencies", "JPY"), ("CL", "Energies", "CRUDE_OIL_WTI"))
MINB = {"A": 150, "L": 150, "N": 250}           # minute bars needed for a valid gold session
SESS = ("A", "L", "N")


def sess_of(hm):
    """hm = bar END minute of the day (ET) -> session."""
    m = (hm - 18 * 60) % 1440
    if 0 < m <= 480:
        return "A"
    if 480 < m <= 840:
        return "L"
    if 840 < m <= 1320:
        return "N"
    return None


# ------------------------------------------------------------------ analysis
def build(days, xkeys):
    """days: sorted list of (date, {asset: {sess: [o, c, hi, lo, n]}}) ->
    list of session observations with features."""
    seq = []
    for d, rec in days:
        g = rec.get("GC", {})
        for s in SESS:
            v = g.get(s)
            if not v or v[4] < MINB[s] or v[0] <= 0:
                continue
            x = {}
            for k in xkeys:
                w = rec.get(k, {}).get(s)
                x[k] = (w[1] / w[0] - 1.0) if (w and w[0] > 0 and w[4] >= 20) else 0.0
            seq.append({"d": d, "s": s, "o": v[0], "r": v[1] / v[0] - 1.0, "hi": v[2] / v[0] - 1.0,
                        "lo": v[3] / v[0] - 1.0, "rng": (v[2] - v[3]) / v[0], "x": x, "c": v[1]})
    closes = []                                  # daily closes (NY session close)
    out = []
    for i, o in enumerate(seq):
        if o["s"] == "A" and i > 0 and seq[i - 1]["s"] == "N":
            pass
        if i >= 60:
            p = [seq[i - k]["r"] for k in (1, 2, 3)]
            same = [q["r"] for q in seq[max(0, i - 20):i] if q["s"] == o["s"]][-5:]
            r60 = [abs(seq[i - k]["r"]) for k in range(1, 61)]
            daily = [sum(seq[j]["r"] for j in range(i - 3 * (k + 1), i - 3 * k)) for k in range(20)]
            f = {"p1": p[0], "p2": p[1], "p3": p[2], "same5": sum(same) / max(1, len(same)),
                 "d1": sum(p), "d5": sum(seq[i - k]["r"] for k in range(1, 16)),
                 "d20": sum(seq[i - k]["r"] for k in range(1, 61)),
                 "vol20": float(np.std(daily)), "vshock": abs(p[0]) / (sum(r60) / 60.0 + 1e-9),
                 "rng1": seq[i - 1]["rng"]}
            if len(closes) >= 50:
                f["sma50"] = closes[-1] / (sum(closes[-50:]) / 50.0) - 1.0
            else:
                f["sma50"] = 0.0
            for k in xkeys:
                f[k + "1"] = seq[i - 1]["x"][k]
                f[k + "d"] = sum(seq[i - j]["x"][k] for j in (1, 2, 3))
            f["gs1"] = p[0] - seq[i - 1]["x"].get("SI", 0.0)
            wd = o["d"].weekday()
            for j in range(5):
                f[f"dow{j}"] = 1.0 if wd == j else 0.0
            f["nfp"] = 1.0 if (wd == 4 and o["d"].day <= 7) else 0.0
            f["tom"] = 1.0 if (o["d"].day <= 2 or o["d"].day >= 28) else 0.0
            o["f"] = f
            out.append(o)
        if o["s"] == "N":
            closes.append(o["c"])
    return out


def ridge_fit(X, y, alpha):
    mu, sd = X.mean(0), X.std(0) + 1e-12
    Z = (X - mu) / sd
    ym = y.mean()
    A = Z.T @ Z + alpha * np.eye(Z.shape[1])
    w = np.linalg.solve(A, Z.T @ (y - ym))
    return lambda Q: ((Q - mu) / sd) @ w + ym


def ridge_cv(X, y, yrs):
    last = sorted(set(yrs))[-2:]
    va = np.isin(yrs, last)
    best, ba = None, 100.0
    if va.sum() > 50 and (~va).sum() > 200:
        for a in (1.0, 10.0, 100.0, 1000.0, 10000.0, 100000.0):
            m = ridge_fit(X[~va], y[~va], a)
            e = np.mean((m(X[va]) - y[va]) ** 2)
            if best is None or e < best:
                best, ba = e, a
    return ridge_fit(X, y, ba), ba


def gbm_fit(X, y):
    try:
        from sklearn.ensemble import HistGradientBoostingRegressor
    except Exception:
        return None
    m = HistGradientBoostingRegressor(max_depth=3, learning_rate=0.03, max_iter=200, min_samples_leaf=100,
                                      l2_regularization=1.0, random_state=1)
    m.fit(X, y)
    return m.predict


def tstat(v):
    v = np.asarray(v)
    return float(v.mean() / (v.std() / math.sqrt(len(v)))) if len(v) > 2 and v.std() > 0 else 0.0


def summ(pnl, mae):
    """compact: hit, mean bp, t, loss<-0.5%, loss<-1%, MAE<-1%, worst."""
    if len(pnl) < 10:
        return "n<10"
    p, m = np.asarray(pnl), np.asarray(mae)
    return (f"hit {np.mean(p > 0) * 100:.1f} {p.mean() * 1e4:+.1f}bp t{tstat(p):+.1f} n{len(p)} "
            f"L.5 {np.mean(p < -0.005) * 100:.1f} L1 {np.mean(p < -0.01) * 100:.1f} "
            f"M1 {np.mean(m < -0.01) * 100:.1f} w{p.min() * 100:.1f}%")


def analyse(days, xkeys):
    obs = build(days, xkeys)
    names = sorted(obs[0]["f"].keys()) if obs else []
    stats = {}
    for s in SESS:
        O = [o for o in obs if o["s"] == s]
        if len(O) < 500:
            continue
        X = np.array([[o["f"][k] for k in names] for o in O])
        y = np.array([o["r"] for o in O])
        hi = np.array([o["hi"] for o in O])
        lo = np.array([o["lo"] for o in O])
        yr = np.array([o["d"].year for o in O])
        ab = np.abs(y)
        P = {"SEAS": np.full(len(y), np.nan), "RIDGE": np.full(len(y), np.nan), "GBM": np.full(len(y), np.nan)}
        CT = {"RIDGE": np.full(len(y), np.nan), "GBM": np.full(len(y), np.nan)}       # confidence threshold
        V = np.full(len(y), np.nan)
        vcols = [names.index(k) for k in names if k in ("p1", "p2", "p3", "vol20", "vshock", "rng1", "nfp", "tom")
                 or k.startswith("dow")]
        alphas = []
        for Y in range(TEST0, int(yr.max()) + 1):
            tr, te = yr < Y, yr == Y
            if te.sum() == 0 or tr.sum() < 300:
                continue
            P["SEAS"][te] = np.sign(y[tr].mean())
            m, a = ridge_cv(X[tr], y[tr], yr[tr])
            alphas.append(a)
            P["RIDGE"][te] = m(X[te])
            CT["RIDGE"][te] = np.percentile(np.abs(m(X[tr])), 80)
            g = gbm_fit(X[tr], y[tr])
            if g is not None:
                P["GBM"][te] = g(X[te])
                CT["GBM"][te] = np.percentile(np.abs(g(X[tr])), 80)
            Xa = np.column_stack([np.abs(X[:, vcols])])
            vm, _ = ridge_cv(Xa[tr], ab[tr], yr[tr])
            V[te] = vm(Xa[te])
        oos = yr >= TEST0
        mae_long = lo
        mae_short = -hi
        out = {}
        out["LONG"] = summ(y[oos], mae_long[oos])
        for k in ("SEAS", "RIDGE", "GBM"):
            ok = oos & ~np.isnan(P[k])
            if ok.sum() < 50:
                continue
            side = np.sign(P[k][ok])
            side[side == 0] = 1.0
            pnl = side * y[ok]
            mae = np.where(side > 0, mae_long[ok], mae_short[ok])
            out[k] = summ(pnl, mae)
            eras = []
            for a_, b_ in ((2013, 2017), (2018, 2021), (2022, 2026)):
                e = (yr[ok] >= a_) & (yr[ok] <= b_)
                if e.sum() > 20:
                    eras.append(f"{a_ % 100}-{b_ % 100} {np.mean(pnl[e] > 0) * 100:.1f}/{pnl[e].mean() * 1e4:+.1f}")
            if k != "SEAS":
                c = np.corrcoef(P[k][ok], y[ok])[0, 1]
                eras.append(f"corr {c:+.3f}")
                conf = np.abs(P[k][ok]) >= CT[k][ok]
                if conf.sum() > 20:
                    out[k + " conf"] = summ(pnl[conf], mae[conf])
            out[k + " era"] = " | ".join(eras)
        okb = oos & ~np.isnan(P["RIDGE"]) & ~np.isnan(P["GBM"])
        if okb.sum() > 50:
            agree = okb & (np.sign(P["RIDGE"]) == np.sign(P["GBM"]))
            side = np.sign(P["RIDGE"][agree])
            pnl = side * y[agree]
            mae = np.where(side > 0, mae_long[agree], mae_short[agree])
            out["AGREE"] = summ(pnl, mae) + f" of {okb.sum()}"
        okv = oos & ~np.isnan(V)
        if okv.sum() > 100:
            c = np.corrcoef(V[okv], ab[okv])[0, 1]
            q = np.percentile(V[okv], [20, 80])
            lo20, hi20 = V[okv] <= q[0], V[okv] >= q[1]
            big = ab[okv] > 0.01
            out["VOL"] = (f"corr pred|r| vs |r| {c:+.3f}; |r|>1%: all {np.mean(big) * 100:.1f}, low20 "
                          f"{np.mean(big[lo20]) * 100:.1f}, high20 {np.mean(big[hi20]) * 100:.1f}; "
                          f"|r|>.5%: low20 {np.mean(ab[okv][lo20] > 0.005) * 100:.1f} high20 "
                          f"{np.mean(ab[okv][hi20] > 0.005) * 100:.1f}")
            # long-only bad days by predicted volatility (does skipping high-vol sessions help?)
            yl = y[okv]
            out["VOL long"] = (f"long low80: {summ(yl[~hi20], lo[okv][~hi20])[:60]} | high20 L1 "
                               f"{np.mean(yl[hi20] < -0.01) * 100:.1f}")
        # univariate (whole sample 2010+), sign by era
        uni = []
        for j, k in enumerate(names):
            col = X[:, j]
            if col.std() == 0:
                continue
            c = np.corrcoef(col, y)[0, 1]
            sg = ""
            for a_, b_ in ((2010, 2015), (2016, 2020), (2021, 2026)):
                e = (yr >= a_) & (yr <= b_)
                ce = np.corrcoef(col[e], y[e])[0, 1] if e.sum() > 50 and col[e].std() > 0 else 0.0
                sg += "+" if ce > 0 else "-"
            uni.append((abs(c) * math.sqrt(len(y)), k, c, sg))
        uni.sort(reverse=True)
        out["UNI1"] = " ".join(f"{k} {c:+.3f}{sg}" for t, k, c, sg in uni[:6])
        out["UNI2"] = " ".join(f"{k} {c:+.3f}{sg}" for t, k, c, sg in uni[6:12])
        out["info"] = f"n {len(y)} oos {int(oos.sum())} mean {y.mean() * 1e4:+.2f}bp sd {y.std() * 1e4:.0f}bp ridge alpha {alphas[-1] if alphas else 0:.0f}"
        stats[s] = out
    return stats


class GoldSessionInQC(QCAlgorithm):

    def initialize(self):
        self.set_start_date(*START)
        self.set_end_date(*END)
        self.set_cash(1_000_000)
        self.sym = {}
        for key, grp, name in ASSETS:
            try:
                tk = getattr(getattr(Futures, grp), name)
                f = self.add_future(tk, Resolution.MINUTE, fill_forward=False,
                                    data_normalization_mode=DataNormalizationMode.BACKWARDS_RATIO,
                                    data_mapping_mode=DataMappingMode.OPEN_INTEREST,
                                    contract_depth_offset=0, extended_market_hours=True)
                f.set_filter(0, 180)
                self.sym[key] = f.symbol
            except Exception as e:
                self.debug(f"skip {key}: {e}")
        self.days = {}

    def on_data(self, data: Slice):
        t = self.time
        s = sess_of(t.hour * 60 + t.minute)
        if s is None:
            return
        D = (t + timedelta(hours=6)).date()
        for key, sy in self.sym.items():
            b = data.bars.get(sy)
            if b is None:
                continue
            o, h, l, c = float(b.open), float(b.high), float(b.low), float(b.close)
            rec = self.days.setdefault(D, {}).setdefault(key, {})
            v = rec.get(s)
            if v is None:
                rec[s] = [o, c, h, l, 1]
            else:
                v[1] = c
                v[2] = max(v[2], h)
                v[3] = min(v[3], l)
                v[4] += 1

    def on_end_of_algorithm(self):
        days = sorted(self.days.items())
        xkeys = [k for k in self.sym if k != "GC"]
        st = analyse(days, xkeys)
        self.set_runtime_statistic("GS assets", ",".join(self.sym.keys()) + f" days {len(days)}")
        for s, out in st.items():
            for k, v in out.items():
                self.set_runtime_statistic(f"GS {s} {k}", v[:195])
