# region imports
from AlgorithmImports import *
import math
from collections import deque
# endregion
#
# "STANDARD DEVIATION CHANNELS" (owner 2026-11-20, Tradovate indicator LIAM_TRADES, file in
# strategy/owner_sources/). The file is only an indicator: linear regression of the close over the last
# N = 100 bars, bands = regression endpoint +- k x stdev(close over the same 100 bars) for k = 1 / 2 / 3
# (note: the stdev of the PRICES, not of the residuals). No trading rules given -> the usual ways to use
# it, FIXED BEFORE RESULTS, on NQ minute data 2010-2026 INSIDE QuantConnect (aggregates only):
#   channel recomputed at every bar close from past bars only (no repaint): m = regression value at the
#   last bar, sd = population stdev of the 100 closes; bars built on the ET clock, all hours; window
#   reset at a contract roll.
#   MR2   close crosses beyond +-2 sd (previous close inside) -> fade: entry next minute open, TP = m,
#         SL = the +-3 sd band (both fixed at the signal)
#   MR3   the same at +-3 sd, SL +-4 sd
#   MR2T  MR2 only in the direction of the regression slope (long at -2 sd if slope > 0, short at
#         +2 sd if slope < 0)
#   BO2   close crosses beyond +-2 sd -> go WITH it: TP +-3 sd, SL +-1 sd
#   timeframes 1 / 5 / 15 min; signals on bars closing 09:35..15:45 ET (RTH), one position per variant,
#   exits on minute bars (stop first, gaps at the open), flat 15:55 ET. Skip if the entry is already
#   beyond the TP or SL. Costs $15 per NQ trade. R = net / initial risk; $ per NQ at today's price
#   (28,530); eras 2010-13 / 14-17 / 18-21 / 22-26.

START = (2010, 1, 1)
END = (2026, 12, 31)
PRICE, PV, COST = 28530.0, 20.0, 15.0
N = 100
TFS = (1, 5, 15)
RULES = ("MR2", "MR3", "MR2T", "BO2")
ERAS = ((2010, 2013), (2014, 2017), (2018, 2021), (2022, 2026))


def era_of(y):
    for i, (a, b) in enumerate(ERAS):
        if a <= y <= b:
            return i
    return None


class Chan:
    """Rolling least-squares line + stdev over the last N closes with O(1) updates
    (running sums, recomputed exactly every 5,000 pushes against float drift)."""
    def __init__(self, tf):
        self.tf = tf
        self.win = deque()
        self.m = self.sd = self.slope = None
        self.prev = None
        self.sy = self.syy = self.s1 = 0.0
        self.k = 0

    def reset(self):
        self.win.clear()
        self.sy = self.syy = self.s1 = 0.0
        self.m = self.sd = self.slope = None
        self.prev = None

    def _exact(self):
        self.sy = sum(self.win)
        self.syy = sum(y * y for y in self.win)
        self.s1 = sum(i * y for i, y in enumerate(self.win))

    def push(self, y):
        if len(self.win) < N:
            self.s1 += len(self.win) * y
            self.sy += y
            self.syy += y * y
            self.win.append(y)
        else:
            y0 = self.win.popleft()
            self.s1 = self.s1 - (self.sy - y0) + (N - 1) * y
            self.sy += y - y0
            self.syy += y * y - y0 * y0
            self.win.append(y)
        self.k += 1
        if self.k % 5000 == 0:
            self._exact()
        if len(self.win) < N:
            self.m = None
            return
        n = float(N)
        ym = self.sy / n
        xm = (n - 1) / 2.0
        b1 = (self.s1 - xm * self.sy) / (n * (n * n - 1) / 12.0)
        self.slope = b1
        self.m = ym + b1 * (n - 1 - xm)
        self.sd = math.sqrt(max(0.0, self.syy / n - ym * ym))


class Var:
    def __init__(self, key):
        self.key = key
        self.pos = None
        self.pending = None
        self.trades = []         # (r, usd, era, year)


class SDChannel(QCAlgorithm):

    def initialize(self):
        self.set_start_date(*START)
        self.set_end_date(*END)
        self.set_cash(1_000_000)
        self.f = self.add_future(Futures.Indices.NASDAQ_100_E_MINI, Resolution.MINUTE, fill_forward=False,
                                 data_normalization_mode=DataNormalizationMode.RAW,
                                 data_mapping_mode=DataMappingMode.OPEN_INTEREST,
                                 contract_depth_offset=0, extended_market_hours=True)
        self.f.set_filter(0, 180)
        self.ch = {tf: Chan(tf) for tf in TFS}
        self.vars = {(r, tf): Var((r, tf)) for r in RULES for tf in TFS}
        self.mapped = None

    def _book(self, v, px, t):
        p = v.pos
        net = (px - p["e"]) * p["d"] - COST / PV
        v.trades.append((net / p["risk"], net * PRICE / p["e"] * PV, era_of(t.year), t.year))
        v.pos = None

    def on_data(self, data: Slice):
        bar = data.bars.get(self.f.symbol)
        if bar is None:
            return
        t = self.time
        m = t.hour * 60 + t.minute
        o, h, l, c = float(bar.open), float(bar.high), float(bar.low), float(bar.close)
        if self.mapped is not None and self.f.mapped != self.mapped:
            for v in self.vars.values():
                if v.pos is not None:
                    self._book(v, c, t)
                v.pending = None
            for ch in self.ch.values():
                ch.reset()
        self.mapped = self.f.mapped
        rth = 9 * 60 + 30 < m <= 16 * 60
        # entries at this minute's open, then exits
        for v in self.vars.values():
            if v.pending is not None and v.pos is None:
                d, tp, sl = v.pending
                v.pending = None
                if rth and m <= 15 * 60 + 50 and (tp - o) * d > 0 and (o - sl) * d > 0:
                    v.pos = {"d": d, "e": o, "tp": tp, "sl": sl, "risk": (o - sl) * d}
            p = v.pos
            if p is None:
                continue
            if p["d"] == 1:
                if l <= p["sl"]:
                    self._book(v, min(p["sl"], o), t)
                elif h >= p["tp"]:
                    self._book(v, max(p["tp"], o), t)
            else:
                if h >= p["sl"]:
                    self._book(v, max(p["sl"], o), t)
                elif l <= p["tp"]:
                    self._book(v, min(p["tp"], o), t)
            if v.pos is not None and (m >= 15 * 60 + 55 or not rth):
                self._book(v, c, t)
        # bar closes per timeframe (ET clock, all hours except the 17:00-18:00 halt)
        for tf, ch in self.ch.items():
            if m % tf != 0:
                continue
            ch.push(c)
            if ch.m is None:
                ch.prev = None
                continue
            cur = (c, ch.m, ch.sd)
            pr = ch.prev
            ch.prev = cur
            if pr is None or not (9 * 60 + 35 <= m <= 15 * 60 + 45) or ch.sd <= 0:
                continue
            pc, pm, psd = pr
            mm, sd = ch.m, ch.sd
            for r in RULES:
                v = self.vars[(r, tf)]
                if v.pos is not None or v.pending is not None:
                    continue
                k = 3.0 if r == "MR3" else 2.0
                up = c > mm + k * sd and pc <= pm + k * psd
                dn = c < mm - k * sd and pc >= pm - k * psd
                if not (up or dn):
                    continue
                if r in ("MR2", "MR3", "MR2T"):
                    d = -1 if up else 1
                    if r == "MR2T" and not ((d == 1 and ch.slope > 0) or (d == -1 and ch.slope < 0)):
                        continue
                    v.pending = (d, mm, mm - d * (k + 1.0) * sd)
                else:
                    d = 1 if up else -1
                    v.pending = (d, mm + d * 3.0 * sd, mm + d * 1.0 * sd)

    def on_end_of_algorithm(self):
        for (r, tf), v in self.vars.items():
            tr = v.trades
            if len(tr) < 20:
                continue
            n = len(tr)
            yrs = max(1.0, len(set(x[3] for x in tr)))
            usd = [x[1] for x in tr]
            mu = sum(usd) / n
            sd = math.sqrt(sum((x - mu) ** 2 for x in usd) / (n - 1))
            win = sum(1 for x in usd if x > 0) / n * 100
            era = " ".join(f"{sum(x[0] for x in tr if x[2] == i) / max(1, sum(1 for x in tr if x[2] == i)):+.2f}" for i in range(len(ERAS)))
            cum = pk = mdd = 0.0
            for x in usd:
                cum += x
                pk = max(pk, cum)
                mdd = min(mdd, cum - pk)
            self.set_runtime_statistic(f"SD {r} {tf}m",
                f"{n / yrs:.0f}/y win {win:.0f}% {sum(x[0] for x in tr) / n:+.3f}R ${mu:+.0f}/tr t{mu / (sd / math.sqrt(n)):+.1f} "
                f"${sum(usd) / yrs:+,.0f}/y DD ${mdd:,.0f} | R era {era}")
