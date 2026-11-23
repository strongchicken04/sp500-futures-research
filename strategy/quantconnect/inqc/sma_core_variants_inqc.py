# region imports
from AlgorithmImports import *
import math
# endregion
#
# CORE ETF: SMA200 RULE VARIANTS (owner 2026-11-23: "for IWDA selling just below the SMA200 after a long rise
# looks illogical"). SPY (2006-2026, incl. 2008) and ACWI (2009-2026) total-return daily, INSIDE QuantConnect,
# aggregates only; trade at the signal close, 2 bp per switch, cash 0% (and 2% shown for SMA). FIXED BEFORE
# RESULTS:
#   BH      buy and hold
#   SMA     out when the daily close < SMA200, back in when > SMA200 (the current plan)
#   BAND2 / BAND3  out only when the close < SMA200 x (1 - 2% / 3%), back in when the close > SMA200
#   WEEKLY  decided only on the last close of each week (above / below SMA200)
#   HALF    50% buy and hold + 50% SMA
# Metrics: CAGR, max DD, switches a year, 2008 / 2020 / 2022 return, share of exits that were re-bought higher
#   within 30 trading days (whipsaw rate), CAGR with cash at 2% for SMA.

class SMACore(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2026, 1, 2)
        self.set_end_date(2026, 1, 3)
        self.set_cash(100000)
        self.syms = {t: self.add_equity(t, Resolution.DAILY).symbol for t in ("SPY", "ACWI")}

    def _run(self, dates, px, sma, i0, mode, cash_y=0.0):
        V = 1.0
        e = 0.0
        vals = []
        sw = 0
        exits = []
        n = len(px)
        for i in range(i0, n):
            if i > i0:
                r = px[i] / px[i - 1] - 1.0
                if mode == "HALF":
                    V *= 1.0 + 0.5 * r + 0.5 * (e * r + (1 - e) * cash_y / 252.0)
                elif mode == "BH":
                    V *= 1.0 + r
                else:
                    V *= 1.0 + e * r + (1 - e) * cash_y / 252.0
            if mode == "BH":
                vals.append(V)
                continue
            ne = e
            if mode in ("SMA", "HALF"):
                ne = 1.0 if px[i] > sma[i] else 0.0
            elif mode in ("BAND2", "BAND3"):
                b = 0.02 if mode == "BAND2" else 0.03
                if e > 0 and px[i] < sma[i] * (1 - b):
                    ne = 0.0
                elif e == 0 and px[i] > sma[i]:
                    ne = 1.0
            elif mode == "WEEKLY":
                last_of_week = i == n - 1 or dates[i + 1].isocalendar()[1] != dates[i].isocalendar()[1]
                if last_of_week or i == i0:
                    ne = 1.0 if px[i] > sma[i] else 0.0
            if ne != e:
                sw += 1
                w = 0.5 if mode == "HALF" else 1.0
                V *= 1.0 - 0.0002 * w
                if ne == 0.0:
                    exits.append((i, px[i]))
                e = ne
            vals.append(V)
        # whipsaw: exit followed by a re-entry within 30 days at a higher price
        ws = 0
        for (ix, p) in exits:
            for j in range(ix + 1, min(n, ix + 31)):
                if mode == "WEEKLY":
                    pass
                if px[j] > sma[j] and px[j] > p:
                    ws += 1
                    break
        return vals, sw, exits, ws

    def on_end_of_algorithm(self):
        for tk, sym in self.syms.items():
            h = self.history(sym, datetime(2003, 1, 1), datetime(2026, 12, 31), Resolution.DAILY)
            px = [float(x) for x in h["close"].values]
            dates = [(ix[1] if isinstance(ix, tuple) else ix).date() for ix in h.index]
            cs = [0.0]
            for x in px:
                cs.append(cs[-1] + x)
            sma = [(cs[i + 1] - cs[max(0, i - 199)]) / (i + 1 - max(0, i - 199)) for i in range(len(px))]
            i0 = 260
            while dates[i0].year < 2006:
                i0 += 1
            yrs = (len(px) - i0) / 252.0
            self.set_runtime_statistic(f"SC {tk} info", f"{dates[i0]}..{dates[-1]} ({yrs:.1f} y)")
            for mode in ("BH", "SMA", "BAND2", "BAND3", "WEEKLY", "HALF"):
                vals, sw, exits, ws = self._run(dates, px, sma, i0, mode)
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
                ys = " ".join(f"{y}:{yr(y):+.0f}%" for y in (2008, 2020, 2022, 2025) if yr(y) is not None)
                extra = ""
                if mode == "SMA":
                    v2, _, _, _ = self._run(dates, px, sma, i0, mode, 0.02)
                    extra = f" | cash2% CAGR {(v2[-1] ** (1 / yrs) - 1) * 100:.1f}%"
                self.set_runtime_statistic(f"SC {tk} {mode}",
                    f"CAGR {cagr * 100:.1f}% DD {mdd * 100:.0f}% | switches {sw / yrs:.1f}/y exits {len(exits)} whipsaw {ws}/{len(exits)} | {ys}{extra}")
