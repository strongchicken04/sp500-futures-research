# region imports
from AlgorithmImports import *
import math
# endregion
#
# 90,000 CZK INVESTMENT MIX (owner 2026-11-23: "test it, keep the topic open - we can come up with new and better
# variants"). Daily adjusted closes (total return) of SPY, EFA, IEF, GLD and BTCUSD, INSIDE QuantConnect,
# aggregates only. Positions set at the close of day t earn t -> t+1; 2 bp per unit of exposure changed; cash
# 0%; leverage above 1x pays 3% a year. FIXED BEFORE RESULTS - plans (weights of the 90k):
#   SPY       100% SPY at the start, hold
#   6040      60% SPY / 40% IEF, rebalanced every 12 months
#   PROP      owner proposal: 55k core SPY bought on the first month start above its SMA200 (max wait 12 months)
#             then held; 15k sleeve SMA200 + RSI2 boost on SPY (1x above SMA200, +0.5x while an RSI2 trade is
#             open: close > SMA200 and RSI2 < 10, exit close > SMA5; max 1.5x); 12k GLD DCA 1/10 a month for
#             10 months, then held; 8k BTC DCA 1/10 a month for 10 months, each tranche only when BTC > SMA200
#             (else deferred; deferred cash goes in at the first month start above), then held; no rebalancing
#   PROP-R    PROP + rebalance to 55 / 15 / 12 / 8 every 12 months (from month 12)
#   TREND     same weights, every sleeve held only above its own SMA200 (SPY, GLD, BTC; daily check), the SPY
#             RSI2 sleeve as in PROP; rebalance every 12 months
#   INVVOL    SPY / GLD / IEF / BTC weighted by inverse 60-day volatility, rebalanced monthly
#   GEM       Antonacci dual momentum, monthly: if SPY 12-month return > 0 hold the better of SPY / EFA
#             (12-month return), else IEF
# v2 (owner 2026-11-23 "so the recommendation is TREND? - run it"): practical TREND versions, FIXED BEFORE
#   RESULTS: SMA200 check daily (D) or at month starts only (M); the 15k sleeve = SMA200 + RSI2 boost with
#   leverage (R) or no leverage (N: the 15k simply joins the SMA200 core); BTC weight 4 / 8 / 12% (the rest of
#   the 8% to the core); C2 = uninvested cash earns 2% a year (else 0%). Yearly rebalance.
#   Plans: TD-R8 (= v1 TREND), TM-R8, TD-N8, TM-N8, TM-N4, TM-N12, TM-N8-C2, + SPY and PROP-R references.
# Run A: with BTC, from the first month start where all series and their SMA200 exist (~2016). Run B: no BTC
#   (BTC weight added to the core / dropped from INVVOL), from 2006-01. Metrics: CAGR, max DD, Sharpe (rf 0),
#   2022, 2008 (run B), worst 12 months; rolling 3-year windows (starts every 3 months): median / worst 3y
#   return and median max DD.

def sma(xs, i, n):
    a = max(0, i - n + 1)
    return sum(xs[a:i + 1]) / (i + 1 - a)


class PortfolioMix(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2026, 1, 2)
        self.set_end_date(2026, 1, 3)
        self.set_cash(100000)
        self.eq = {t: self.add_equity(t, Resolution.DAILY).symbol for t in ("SPY", "EFA", "IEF", "GLD")}
        self.btc = self.add_crypto("BTCUSD", Resolution.DAILY, Market.COINBASE).symbol

    # ------------------------------------------------------------------ data
    def _series(self):
        out = {}
        for t, s in self.eq.items():
            h = self.history(s, datetime(2003, 1, 1), datetime(2026, 12, 31), Resolution.DAILY)
            out[t] = {(ix[1] if isinstance(ix, tuple) else ix).date(): float(v) for ix, v in zip(h.index, h["close"].values)}
        h = self.history(self.btc, datetime(2014, 1, 1), datetime(2026, 12, 31), Resolution.DAILY)
        out["BTC"] = {(ix[1] if isinstance(ix, tuple) else ix).date(): float(v) for ix, v in zip(h.index, h["close"].values)} if h is not None and not h.empty else {}
        return out

    def _align(self, raw, assets):
        dates = sorted(raw["SPY"].keys())
        px = {a: [] for a in assets}
        last = {a: None for a in assets}
        keep = []
        bd = sorted(raw["BTC"].keys()) if "BTC" in assets else []
        bi = 0
        for d in dates:
            ok = True
            for a in assets:
                if a == "BTC":
                    while bi < len(bd) and bd[bi] <= d:
                        last[a] = raw["BTC"][bd[bi]]
                        bi += 1
                else:
                    v = raw[a].get(d)
                    if v is not None:
                        last[a] = v
                if last[a] is None:
                    ok = False
            if ok:
                keep.append(d)
                for a in assets:
                    px[a].append(last[a])
        return keep, px

    # ------------------------------------------------------------------ simulation
    def _rsi2(self, xs):
        out = [50.0] * len(xs)
        g = l = None
        for i in range(1, len(xs)):
            ch = xs[i] - xs[i - 1]
            up, dn = max(ch, 0.0), max(-ch, 0.0)
            if g is None:
                g, l = up, dn
            else:
                g += (up - g) / 2.0
                l += (dn - l) / 2.0
            out[i] = 100.0 if l == 0 else 100.0 - 100.0 / (1.0 + g / l)
        return out

    def _sim(self, dates, px, plan, i0, i1, with_btc):
        """Daily portfolio values from i0 to i1 (inclusive), start value 1."""
        spy, gld = px["SPY"], px["GLD"]
        btc = px.get("BTC")
        ms = set(i for i in range(i0, i1 + 1) if i == i0 or dates[i].month != dates[i - 1].month)
        msl = sorted(ms)
        vals = []
        cost = 0.0002
        if plan == "SPY":
            for i in range(i0, i1 + 1):
                vals.append(spy[i] / spy[i0])
            return vals
        if plan in ("6040", "GEM", "INVVOL"):
            V = 1.0
            w = {}
            start_m = 0
            for i in range(i0, i1 + 1):
                if i > i0:
                    V *= 1.0 + sum(w[a] * (px[a][i] / px[a][i - 1] - 1.0) for a in w)
                if i in ms:
                    k = msl.index(i)
                    nw = w
                    if plan == "6040" and (k % 12 == 0):
                        nw = {"SPY": 0.6, "IEF": 0.4}
                    elif plan == "GEM":
                        j = max(0, i - 252)
                        rs = px["SPY"][i] / px["SPY"][j] - 1.0
                        re = px["EFA"][i] / px["EFA"][j] - 1.0
                        nw = {("SPY" if rs >= re else "EFA"): 1.0} if rs > 0 else {"IEF": 1.0}
                    elif plan == "INVVOL":
                        assets = ["SPY", "GLD", "IEF"] + (["BTC"] if with_btc else [])
                        iv = {}
                        for a in assets:
                            rr = [px[a][x] / px[a][x - 1] - 1.0 for x in range(max(1, i - 59), i + 1)]
                            m = sum(rr) / len(rr)
                            sd = math.sqrt(sum((r - m) ** 2 for r in rr) / max(1, len(rr) - 1)) or 1e-6
                            iv[a] = 1.0 / sd
                        s = sum(iv.values())
                        nw = {a: iv[a] / s for a in assets}
                    if nw is not w:
                        ch = sum(abs(nw.get(a, 0) - w.get(a, 0)) for a in set(nw) | set(w))
                        V *= 1.0 - cost * ch
                        w = nw
                vals.append(V)
            return vals
        # PROP / PROP-R / TREND: sleeves
        wts = {"core": 55.0, "rsi": 15.0, "gold": 12.0, "btc": 8.0}
        if not with_btc:
            wts = {"core": 63.0, "rsi": 15.0, "gold": 12.0}
        tot = sum(wts.values())
        wts = {k: v / tot for k, v in wts.items()}
        rsi = self._rsi2(spy)
        # sleeve state
        core = {"cash": wts["core"], "u": 0.0, "wait": 0, "V": wts["core"], "e": 0.0}
        sl = {"V": wts["rsi"], "e": 0.0, "trade": False}
        gold = {"cash": wts["gold"], "u": 0.0, "k": 0, "V": wts["gold"], "e": 0.0}
        bt = {"cash": wts.get("btc", 0.0), "u": 0.0, "k": 0, "def": 0.0, "V": wts.get("btc", 0.0), "e": 0.0}
        trend = plan == "TREND"
        for i in range(i0, i1 + 1):
            # returns from i-1 to i
            if i > i0:
                rs = spy[i] / spy[i - 1] - 1.0
                lev = max(0.0, sl["e"] - 1.0) * 0.03 / 252.0
                sl["V"] *= 1.0 + sl["e"] * rs - lev
                if trend:
                    core["V"] *= 1.0 + core["e"] * rs
                    gold["V"] *= 1.0 + gold["e"] * (gld[i] / gld[i - 1] - 1.0)
                    if with_btc:
                        bt["V"] *= 1.0 + bt["e"] * (btc[i] / btc[i - 1] - 1.0)
            # decisions at the close of i
            # RSI2 sleeve
            above = spy[i] > self.S200["SPY"][i]
            if sl["trade"] and spy[i] > self.S5[i]:
                sl["trade"] = False
            if not sl["trade"] and above and rsi[i] < 10:
                sl["trade"] = True
            ne = (1.0 if above else 0.0) + (0.5 if sl["trade"] else 0.0)
            sl["V"] *= 1.0 - cost * abs(ne - sl["e"])
            sl["e"] = ne
            if trend:
                if i == i0:
                    core["V"], gold["V"] = core["cash"], gold["cash"]
                    bt["V"] = bt["cash"]
                for st, p, nm in ((core, spy, "SPY"), (gold, gld, "GLD")) + (((bt, btc, "BTC"),) if with_btc else ()):
                    ne2 = 1.0 if p[i] > self.S200[nm][i] else 0.0
                    st["V"] *= 1.0 - cost * abs(ne2 - st["e"])
                    st["e"] = ne2
            elif i in ms:
                k = msl.index(i)
                # core: first month start above SMA200 (max 12 months)
                if core["cash"] > 0 and (above or k >= 11):
                    core["u"] += core["cash"] * (1 - cost) / spy[i]
                    core["cash"] = 0.0
                # gold DCA
                if gold["k"] < 10 and gold["cash"] > 0:
                    b = min(gold["cash"], wts["gold"] / 10.0) if gold["k"] < 9 else gold["cash"]
                    gold["u"] += b * (1 - cost) / gld[i]
                    gold["cash"] -= b
                    gold["k"] += 1
                # BTC DCA gated by SMA200
                if with_btc and bt["cash"] > 1e-12:
                    if bt["k"] < 10:
                        bt["def"] += wts["btc"] / 10.0
                        bt["k"] += 1
                    if btc[i] > self.S200["BTC"][i]:
                        b = min(bt["cash"], bt["def"] if bt["k"] < 10 else bt["cash"])
                        bt["u"] += b * (1 - cost) / btc[i]
                        bt["cash"] -= b
                        bt["def"] = max(0.0, bt["def"] - b)
            # value
            if trend:
                V = core["V"] + sl["V"] + gold["V"] + (bt["V"] if with_btc else 0.0)
            else:
                V = core["cash"] + core["u"] * spy[i] + sl["V"] + gold["cash"] + gold["u"] * gld[i]
                if with_btc:
                    V += bt["cash"] + bt["u"] * btc[i]
            # yearly rebalance (PROP-R, TREND) from month 12 on
            if plan in ("PROP-R", "TREND") and i in ms and msl.index(i) > 0 and msl.index(i) % 12 == 0:
                if trend:
                    core["V"], sl["V"], gold["V"] = wts["core"] * V, wts["rsi"] * V, wts["gold"] * V
                    if with_btc:
                        bt["V"] = wts["btc"] * V
                else:
                    core["u"], core["cash"] = wts["core"] * V / spy[i], 0.0
                    sl["V"] = wts["rsi"] * V
                    gold["u"], gold["cash"] = wts["gold"] * V / gld[i], 0.0
                    if with_btc:
                        bt["u"], bt["cash"], bt["def"] = wts["btc"] * V / btc[i], 0.0, 0.0
                V *= 1.0 - cost * 0.2
            vals.append(V / 1.0)
        return vals


    def _trend(self, dates, px, i0, i1, with_btc, check, lev, wbtc, cash_y):
        spy, gld = px["SPY"], px["GLD"]
        btc = px.get("BTC")
        cost = 0.0002
        ms = set(i for i in range(i0, i1 + 1) if i == i0 or dates[i].month != dates[i - 1].month)
        msl = sorted(ms)
        wb = wbtc if with_btc else 0.0
        w = {"core": 55.0 + (8.0 - wb) + (0.0 if lev else 15.0), "rsi": 15.0 if lev else 0.0, "gold": 12.0, "btc": wb}
        tot = sum(w.values())
        w = {k: v / tot for k, v in w.items()}
        rsi = self._rsi2(spy)
        S = {k: {"V": w[k], "e": 0.0} for k in w}
        trade = False
        cy = cash_y / 252.0
        vals = []
        for i in range(i0, i1 + 1):
            if i > i0:
                for k, p in (("core", spy), ("gold", gld), ("btc", btc)):
                    if w[k] <= 0:
                        continue
                    r = p[i] / p[i - 1] - 1.0
                    S[k]["V"] *= 1.0 + S[k]["e"] * r + (1.0 - S[k]["e"]) * cy
                if w["rsi"] > 0:
                    r = spy[i] / spy[i - 1] - 1.0
                    e = S["rsi"]["e"]
                    S["rsi"]["V"] *= 1.0 + e * r + max(0.0, 1.0 - e) * cy - max(0.0, e - 1.0) * 0.03 / 252.0
            mstart = i in ms
            for k, p, nm in (("core", spy, "SPY"), ("gold", gld, "GLD"), ("btc", btc, "BTC")):
                if w[k] <= 0:
                    continue
                if check == "D" or mstart:
                    ne = 1.0 if p[i] > self.S200[nm][i] else 0.0
                    S[k]["V"] *= 1.0 - cost * abs(ne - S[k]["e"])
                    S[k]["e"] = ne
            if w["rsi"] > 0:
                above = spy[i] > self.S200["SPY"][i]
                if trade and spy[i] > self.S5[i]:
                    trade = False
                if not trade and above and rsi[i] < 10:
                    trade = True
                ne = (1.0 if above else 0.0) + (0.5 if trade else 0.0)
                S["rsi"]["V"] *= 1.0 - cost * abs(ne - S["rsi"]["e"])
                S["rsi"]["e"] = ne
            V = sum(S[k]["V"] for k in w if w[k] > 0)
            if mstart and msl.index(i) > 0 and msl.index(i) % 12 == 0:
                for k in w:
                    if w[k] > 0:
                        S[k]["V"] = w[k] * V
                V *= 1.0 - cost * 0.2
                for k in w:
                    if w[k] > 0:
                        S[k]["V"] *= 1.0 - cost * 0.2
            vals.append(V)
        return vals

    def _run(self, dates, px, p, i0, i1, with_btc):
        if p.startswith("T") and "-" in p:
            check = p[1]
            rest = p.split("-")[1]
            lev = rest[0] == "R"
            wbtc = float(rest[1:])
            cy = 0.02 if p.endswith("C2") else 0.0
            return self._trend(dates, px, i0, i1, with_btc, check, lev, wbtc, cy)
        return self._sim(dates, px, p, i0, i1, with_btc)

    def _stats(self, dates, vals, i0):
        n = len(vals)
        yrs = n / 252.0
        cagr = vals[-1] ** (1 / yrs) - 1 if yrs > 0 else 0
        pk, mdd = vals[0], 0.0
        for v in vals:
            pk = max(pk, v)
            mdd = min(mdd, v / pk - 1)
        r = [vals[i] / vals[i - 1] - 1 for i in range(1, n)]
        m = sum(r) / len(r)
        sd = math.sqrt(sum((x - m) ** 2 for x in r) / (len(r) - 1))
        sh = m / sd * math.sqrt(252) if sd > 0 else 0
        def yr(y):
            idx = [k for k in range(n) if dates[i0 + k].year == y]
            if len(idx) < 50:
                return None
            a = idx[0] - 1 if idx[0] > 0 else idx[0]
            return vals[idx[-1]] / vals[a] - 1
        w12 = min(vals[k] / vals[k - 252] - 1 for k in range(252, n)) if n > 252 else 0
        return cagr, mdd, sh, yr(2022), yr(2008), w12

    def on_end_of_algorithm(self):
        raw = self._series()
        plans_a = ("SPY", "PROP-R", "TD-R8", "TM-R8", "TD-N8", "TM-N8", "TM-N4", "TM-N12", "TM-N8-C2")
        plans_b = ("SPY", "PROP-R", "TD-R8", "TM-R8", "TD-N8", "TM-N8", "TM-N8-C2")
        for run, with_btc in (("A", True), ("B", False)):
            assets = ["SPY", "EFA", "IEF", "GLD"] + (["BTC"] if with_btc else [])
            if with_btc and not raw["BTC"]:
                self.set_runtime_statistic("PM A", "no BTC data")
                continue
            dates, px = self._align(raw, assets)
            self.S200 = {}
            for a in assets:
                xs = px[a]
                cs = [0.0]
                for x in xs:
                    cs.append(cs[-1] + x)
                self.S200[a] = [(cs[i + 1] - cs[max(0, i - 199)]) / (i + 1 - max(0, i - 199)) for i in range(len(xs))]
            cs = [0.0]
            for x in px["SPY"]:
                cs.append(cs[-1] + x)
            self.S5 = [(cs[i + 1] - cs[max(0, i - 4)]) / (i + 1 - max(0, i - 4)) for i in range(len(px["SPY"]))]
            # first month start with >= 260 days of history for every series
            i_first = 260
            if not with_btc:
                while dates[i_first].year < 2006:
                    i_first += 1
            while i_first < len(dates) and dates[i_first].month == dates[i_first - 1].month:
                i_first += 1
            i_end = len(dates) - 1
            self.set_runtime_statistic(f"PM {run} info", f"{dates[i_first]}..{dates[i_end]} ({(i_end - i_first) / 252:.1f} y)")
            starts = [i for i in range(i_first, i_end - 756) if dates[i].month != dates[i - 1].month and dates[i].month in (1, 4, 7, 10)]
            for p in (plans_a if with_btc else plans_b):
                vals = self._run(dates, px, p, i_first, i_end, with_btc)
                cagr, mdd, sh, y22, y08, w12 = self._stats(dates, vals, i_first)
                r3, d3 = [], []
                for s0 in starts:
                    v3 = self._run(dates, px, p, s0, s0 + 756, with_btc)
                    r3.append(v3[-1] / v3[0] - 1)
                    pk, md = v3[0], 0.0
                    for v in v3:
                        pk = max(pk, v)
                        md = min(md, v / pk - 1)
                    d3.append(md)
                r3s, d3s = sorted(r3), sorted(d3)
                self.set_runtime_statistic(f"PM {run} {p}",
                    f"CAGR {cagr * 100:.1f}% DD {mdd * 100:.0f}% Sharpe {sh:.2f} | 2022 {y22 * 100 if y22 is not None else 0:+.0f}%"
                    + (f" 2008 {y08 * 100:+.0f}%" if y08 is not None else "")
                    + f" worst12m {w12 * 100:+.0f}% | 3y med {r3s[len(r3s) // 2] * 100:+.0f}% worst {r3s[0] * 100:+.0f}% medDD {d3s[len(d3s) // 2] * 100:.0f}%")
