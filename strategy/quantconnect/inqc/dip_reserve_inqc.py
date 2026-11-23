# region imports
from AlgorithmImports import *
import math
# endregion
#
# DIP RESERVE ABOVE THE SMA200 (owner 2026-11-23: "test the dip-reserve-above-SMA200 version"). SPY 2006-2026,
# ACWI 2009-2026, GLD 2006-2026, total-return daily, INSIDE QuantConnect, aggregates only; trades at the signal
# close, 2 bp per change, cash 0%. FIXED BEFORE RESULTS (fractions of one sleeve):
#   BH      100% held
#   HOLD80  80% held + 20% cash (fair comparison for a 20% reserve)
#   RSI2    80% held; the 20% reserve goes in when close > SMA200 and RSI(2) < 10, out when close > SMA5
#   DD5 / DD10  80% held; the reserve goes in when the close is >= 5% / 10% below the 252-day high AND above
#           the SMA200; out when the close is back within 1% of that high, or below the SMA200
#   WAIT    80% held; the reserve goes in at the first close >= 5% below the 252-day high while above the SMA200,
#           then stays invested for good
# Metrics: CAGR, max DD, share of days the reserve is invested, reserve entries a year, result vs BH and HOLD80.

class DipReserve(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2026, 1, 2)
        self.set_end_date(2026, 1, 3)
        self.set_cash(100000)
        self.syms = {t: self.add_equity(t, Resolution.DAILY).symbol for t in ("SPY", "ACWI", "GLD")}

    def on_end_of_algorithm(self):
        for tk, sym in self.syms.items():
            h = self.history(sym, datetime(2003, 1, 1), datetime(2026, 12, 31), Resolution.DAILY)
            px = [float(x) for x in h["close"].values]
            dates = [(ix[1] if isinstance(ix, tuple) else ix).date() for ix in h.index]
            n = len(px)
            cs = [0.0]
            for x in px:
                cs.append(cs[-1] + x)
            s200 = [(cs[i + 1] - cs[max(0, i - 199)]) / (i + 1 - max(0, i - 199)) for i in range(n)]
            s5 = [(cs[i + 1] - cs[max(0, i - 4)]) / (i + 1 - max(0, i - 4)) for i in range(n)]
            hi = [max(px[max(0, i - 251):i + 1]) for i in range(n)]
            rsi = [50.0] * n
            g = l = None
            for i in range(1, n):
                ch = px[i] - px[i - 1]
                up, dn = max(ch, 0.0), max(-ch, 0.0)
                if g is None:
                    g, l = up, dn
                else:
                    g += (up - g) / 2.0
                    l += (dn - l) / 2.0
                rsi[i] = 100.0 if l == 0 else 100.0 - 100.0 / (1.0 + g / l)
            i0 = 260
            while dates[i0].year < 2006:
                i0 += 1
            yrs = (n - i0) / 252.0
            self.set_runtime_statistic(f"DR {tk} info", f"{dates[i0]}..{dates[-1]} ({yrs:.1f} y)")
            res = {}
            for mode in ("BH", "HOLD80", "RSI2", "DD5", "DD10", "WAIT"):
                V = 1.0
                core = 1.0 if mode == "BH" else 0.8
                e = 0.0
                inres = 0
                entries = 0
                waited = False
                vals = []
                for i in range(i0, n):
                    if i > i0:
                        r = px[i] / px[i - 1] - 1.0
                        V *= 1.0 + (core + 0.2 * e) * r
                    ne = e
                    above = px[i] > s200[i]
                    dd = px[i] / hi[i] - 1.0
                    if mode == "RSI2":
                        if e > 0 and px[i] > s5[i]:
                            ne = 0.0
                        if ne == 0 and above and rsi[i] < 10:
                            ne = 1.0
                    elif mode in ("DD5", "DD10"):
                        th = -0.05 if mode == "DD5" else -0.10
                        if e > 0 and (dd > -0.01 or not above):
                            ne = 0.0
                        if ne == 0 and above and dd <= th:
                            ne = 1.0
                    elif mode == "WAIT":
                        if not waited and above and dd <= -0.05:
                            ne = 1.0
                            waited = True
                    if ne != e:
                        V *= 1.0 - 0.0002 * 0.2
                        if ne > e:
                            entries += 1
                        e = ne
                    inres += e > 0
                    vals.append(V)
                cagr = vals[-1] ** (1 / yrs) - 1
                pk, mdd = vals[0], 0.0
                for v in vals:
                    pk = max(pk, v)
                    mdd = min(mdd, v / pk - 1)
                res[mode] = (cagr, mdd, inres / len(vals), entries / yrs)
            for mode, (cagr, mdd, tin, ent) in res.items():
                self.set_runtime_statistic(f"DR {tk} {mode}",
                    f"CAGR {cagr * 100:.2f}% DD {mdd * 100:.0f}% | reserve in {tin * 100:.0f}% of days, {ent:.1f} entries/y"
                    f" | vs BH {(cagr - res['BH'][0]) * 100:+.2f}%/y vs HOLD80 {(cagr - res['HOLD80'][0]) * 100:+.2f}%/y")
