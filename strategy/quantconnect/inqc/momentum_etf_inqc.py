# region imports
from AlgorithmImports import *
import math
# endregion
#
# MOMENTUM ETF vs WORLD INDEX (owner 2026-11-23). Total-return daily history INSIDE QuantConnect, aggregates only;
# trades at the signal close, 2 bp per unit changed, cash 0%. FIXED BEFORE RESULTS:
#   Run M (2014-02 .. data end, MTUM inception 2013-04 + SMA200): BH MTUM, BH ACWI, BH SPY, BH URTH (MSCI World),
#     HALF-MTUM / HALF-ACWI (50% held + 50% held only above its SMA200, daily close), and MTUM - ACWI per year.
#   Run S (2000-01 .. data end): sector momentum on the 9 original S&P sector ETFs (XLB XLE XLF XLI XLK XLP XLU
#     XLV XLY): at each month start hold the top 3 by the 12-1 month return (t-252 .. t-21) equally weighted;
#     SEC3F = the same but hold IEF when SPY's 12-month return < 0; vs BH SPY.
# Metrics: CAGR, max DD, Sharpe, 2008 / 2020 / 2022, worst rolling 3-year return.

SECT = ("XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY")


class MomentumETF(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2026, 1, 2)
        self.set_end_date(2026, 1, 3)
        self.set_cash(100000)
        self.tk = ("MTUM", "ACWI", "SPY", "URTH", "IEF") + SECT
        self.syms = {t: self.add_equity(t, Resolution.DAILY).symbol for t in self.tk}

    def _load(self):
        raw = {}
        for t, s in self.syms.items():
            h = self.history(s, datetime(1998, 6, 1), datetime(2026, 12, 31), Resolution.DAILY)
            raw[t] = {(ix[1] if isinstance(ix, tuple) else ix).date(): float(v) for ix, v in zip(h.index, h["close"].values)} if h is not None and not h.empty else {}
        return raw

    def _align(self, raw, assets):
        dates = sorted(set.intersection(*[set(raw[a].keys()) for a in assets]))
        return dates, {a: [raw[a][d] for d in dates] for a in assets}

    def _stats(self, dates, vals):
        n = len(vals)
        yrs = n / 252.0
        cagr = vals[-1] ** (1 / yrs) - 1
        pk, mdd = vals[0], 0.0
        for v in vals:
            pk = max(pk, v)
            mdd = min(mdd, v / pk - 1)
        r = [vals[i] / vals[i - 1] - 1 for i in range(1, n)]
        m = sum(r) / len(r)
        sd = math.sqrt(sum((x - m) ** 2 for x in r) / (len(r) - 1))
        def yr(y):
            idx = [k for k in range(n) if dates[k].year == y]
            if len(idx) < 50:
                return None
            a = max(0, idx[0] - 1)
            return (vals[idx[-1]] / vals[a] - 1) * 100
        w3 = min(vals[k] / vals[k - 756] - 1 for k in range(756, n)) * 100 if n > 756 else 0
        ys = " ".join(f"{y}:{yr(y):+.0f}%" for y in (2008, 2020, 2022) if yr(y) is not None)
        return f"CAGR {cagr * 100:.1f}% DD {mdd * 100:.0f}% Sharpe {m / sd * math.sqrt(252):.2f} | {ys} | worst3y {w3:+.0f}%", yr

    def _bh(self, px, i0):
        return [px[i] / px[i0] for i in range(i0, len(px))]

    def _half(self, px, i0):
        cs = [0.0]
        for x in px:
            cs.append(cs[-1] + x)
        s200 = [(cs[i + 1] - cs[max(0, i - 199)]) / (i + 1 - max(0, i - 199)) for i in range(len(px))]
        V, e, out = 1.0, 0.0, []
        for i in range(i0, len(px)):
            if i > i0:
                r = px[i] / px[i - 1] - 1
                V *= 1 + 0.5 * r + 0.5 * e * r
            ne = 1.0 if px[i] > s200[i] else 0.0
            if ne != e:
                V *= 1 - 0.0001
                e = ne
            out.append(V)
        return out

    def on_end_of_algorithm(self):
        raw = self._load()
        # ---- run M
        dates, px = self._align(raw, ["MTUM", "ACWI", "SPY", "URTH"])
        i0 = 200
        while dates[i0].month == dates[i0 - 1].month:
            i0 += 1
        dm = dates[i0:]
        self.set_runtime_statistic("ME M info", f"{dm[0]}..{dm[-1]} ({len(dm) / 252:.1f} y)")
        yrfun = {}
        for name, vals in (("BH MTUM", self._bh(px["MTUM"], i0)), ("BH ACWI", self._bh(px["ACWI"], i0)),
                           ("BH SPY", self._bh(px["SPY"], i0)), ("BH URTH", self._bh(px["URTH"], i0)),
                           ("HALF MTUM", self._half(px["MTUM"], i0)), ("HALF ACWI", self._half(px["ACWI"], i0))):
            s, yr = self._stats(dm, vals)
            yrfun[name] = yr
            self.set_runtime_statistic(f"ME M {name}", s)
        yrs = sorted(set(d.year for d in dm))
        diffs = []
        for y in yrs:
            a, b = yrfun["BH MTUM"](y), yrfun["BH ACWI"](y)
            c = yrfun["BH SPY"](y)
            if a is not None and b is not None:
                diffs.append(f"{y % 100}:{a - b:+.0f}/{a - c:+.0f}")
        self.set_runtime_statistic("ME M MTUM-ACWI/-SPY by year pp", " ".join(diffs))
        # ---- run S: sector momentum
        dates, px = self._align(raw, list(SECT) + ["SPY", "IEF"])
        i0 = 260
        while dates[i0].month == dates[i0 - 1].month:
            i0 += 1
        ds = dates[i0:]
        self.set_runtime_statistic("ME S info", f"{ds[0]}..{ds[-1]} ({len(ds) / 252:.1f} y)")
        for name in ("SEC3", "SEC3F"):
            V, w, out = 1.0, {}, []
            for i in range(i0, len(dates)):
                if i > i0:
                    V *= 1 + sum(w[a] * (px[a][i] / px[a][i - 1] - 1) for a in w)
                if i == i0 or dates[i].month != dates[i - 1].month:
                    mom = {a: px[a][i - 21] / px[a][i - 252] - 1 for a in SECT}
                    top = sorted(SECT, key=lambda a: mom[a], reverse=True)[:3]
                    nw = {a: 1 / 3 for a in top}
                    if name == "SEC3F" and px["SPY"][i] / px["SPY"][i - 252] - 1 < 0:
                        nw = {"IEF": 1.0}
                    ch = sum(abs(nw.get(a, 0) - w.get(a, 0)) for a in set(nw) | set(w))
                    V *= 1 - 0.0002 * ch
                    w = nw
                out.append(V)
            s, _ = self._stats(ds, out)
            self.set_runtime_statistic(f"ME S {name}", s)
        s, _ = self._stats(ds, self._bh(px["SPY"], i0))
        self.set_runtime_statistic("ME S BH SPY", s)
