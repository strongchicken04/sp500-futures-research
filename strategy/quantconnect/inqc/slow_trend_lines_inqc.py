# region imports
from AlgorithmImports import *
import math
# endregion
#
# SLOWER / LOWER TREND LINES THAN SMA200 (owner 2026-11-24: "is there something like SMA200 but further below the
# price?"). SPY, ACWI, GLD (equities, total return) and BTCUSD daily, INSIDE QuantConnect, aggregates only; trade at
# the signal close, 2 bp per switch, cash 0%. Per asset one common start = the first month where every line exists.
# FIXED BEFORE RESULTS:
#   BH       buy and hold
#   SMA200   out below / in above the SMA200 (current plan)
#   SMA300 / SMA400 / SMA1000 (~200-week)  out below / in above that SMA
#   TS15 / TS20  out when the close <= 252-day high x (1 - 15% / 20%); back in when the close > SMA200
#   DON126   out when the close < the lowest close of the previous 126 days; back in when the close > SMA200
# Metrics: CAGR, max DD, exits a year, vs BH, 2008 / 2020 / 2022.

class SlowLines(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2026, 1, 2)
        self.set_end_date(2026, 1, 3)
        self.set_cash(100000)
        self.syms = {t: self.add_equity(t, Resolution.DAILY).symbol for t in ("SPY", "ACWI", "GLD")}
        self.syms["BTC"] = self.add_crypto("BTCUSD", Resolution.DAILY, Market.COINBASE).symbol

    def on_end_of_algorithm(self):
        for tk, sym in self.syms.items():
            h = self.history(sym, datetime(1998, 1, 1), datetime(2026, 12, 31), Resolution.DAILY)
            if h is None or h.empty:
                continue
            px = [float(x) for x in h["close"].values]
            dates = [(ix[1] if isinstance(ix, tuple) else ix).date() for ix in h.index]
            n = len(px)
            cs = [0.0]
            for x in px:
                cs.append(cs[-1] + x)
            def sma(k):
                return [(cs[i + 1] - cs[max(0, i - k + 1)]) / (i + 1 - max(0, i - k + 1)) for i in range(n)]
            S = {k: sma(k) for k in (200, 300, 400, 1000)}
            hi = [max(px[max(0, i - 251):i + 1]) for i in range(n)]
            lo126 = [min(px[max(0, i - 126):i]) if i > 0 else px[0] for i in range(n)]
            i0 = 1000
            if tk == "SPY":
                while dates[i0].year < 2006:
                    i0 += 1
            while dates[i0].month == dates[i0 - 1].month:
                i0 += 1
            yrs = (n - i0) / 252.0
            self.set_runtime_statistic(f"SL {tk} info", f"{dates[i0]}..{dates[-1]} ({yrs:.1f} y)")
            out = {}
            for mode in ("BH", "SMA200", "SMA300", "SMA400", "SMA1000", "TS15", "TS20", "DON126"):
                V, e, exits, vals = 1.0, 1.0, 0, []
                for i in range(i0, n):
                    if i > i0:
                        V *= 1 + e * (px[i] / px[i - 1] - 1)
                    ne = e
                    if mode.startswith("SMA"):
                        k = int(mode[3:])
                        ne = 1.0 if px[i] > S[k][i] else 0.0
                    elif mode in ("TS15", "TS20"):
                        b = 0.15 if mode == "TS15" else 0.20
                        if e > 0 and px[i] <= hi[i] * (1 - b):
                            ne = 0.0
                        elif e == 0 and px[i] > S[200][i]:
                            ne = 1.0
                    elif mode == "DON126":
                        if e > 0 and px[i] < lo126[i]:
                            ne = 0.0
                        elif e == 0 and px[i] > S[200][i]:
                            ne = 1.0
                    if ne != e:
                        V *= 1 - 0.0002
                        if ne == 0:
                            exits += 1
                        e = ne
                    vals.append(V)
                cagr = vals[-1] ** (1 / yrs) - 1
                pk, mdd = vals[0], 0.0
                for v in vals:
                    pk = max(pk, v)
                    mdd = min(mdd, v / pk - 1)
                def yr(y):
                    idx = [k for k in range(len(vals)) if dates[i0 + k].year == y]
                    if len(idx) < 50:
                        return None
                    a = max(0, idx[0] - 1)
                    return (vals[idx[-1]] / vals[a] - 1) * 100
                ys = " ".join(f"{y}:{yr(y):+.0f}%" for y in (2008, 2020, 2022) if yr(y) is not None)
                out[mode] = cagr
                self.set_runtime_statistic(f"SL {tk} {mode}",
                    f"CAGR {cagr * 100:.1f}% DD {mdd * 100:.0f}% | exits {exits / yrs:.1f}/y | vs BH {(cagr - out['BH']) * 100:+.1f}%/y | {ys}")
