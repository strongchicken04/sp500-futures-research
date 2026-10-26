# region imports
from AlgorithmImports import *
import math
# endregion
#
# VG LEG (Lucid 2, VWAP band break) x REAL ORDER FLOW, computed INSIDE
# QuantConnect (night 2026-10-26/27, rules fixed before results). Exports no
# market data: only aggregate statistics per year as runtime statistics.
#
# VG rules (AUTOMATION_SPEC): 5-min RTH bars; band = session VWAP x (1 +/-
# 0.20%); entry at the 5-min close that leaves the band (previous close inside)
# -> above LONG, below SHORT; first trade of the day; not on Wednesdays; stop
# 25 pt, target 100 pt (first touch on 1-second highs / lows, stop first),
# else flat at 15:55. (The live leg also has the 20-day vol gate - not applied
# here; the comparison is between flow groups on the same signals.)
# Order flow of the breakout 5-min bar: I = (buy - sell) / (buy + sell) of
# aggressive volume (trade close vs quote mid, tick rule at the mid), x the
# break direction. Groups: CONFIRM (I >= +0.20), NEUTRAL, AGAINST (I <= -0.20).
# v2 (after 2023-24 gave only 6-15 CONFIRM and no AGAINST trades a year -
# breakout bars are rarely that one-sided; stated openly): groups by sign
# POS (I > 0) / NEG (I <= 0) and C05 (I >= +0.05) / A05 (I <= -0.05).
# Gross points per trade (per contract), mean / t / n / wins per year.

START = (2020, 1, 1)
END = (2020, 12, 31)
EOD = 955
STOP_PT, TGT_PT = 25.0, 100.0


class VGFlowInQC(QCAlgorithm):

    def initialize(self):
        self.set_start_date(*START)
        self.set_end_date(*END)
        self.set_cash(1_000_000)
        self.nq = self.add_future(Futures.Indices.NASDAQ_100_E_MINI, Resolution.SECOND,
                                  data_normalization_mode=DataNormalizationMode.RAW,
                                  data_mapping_mode=DataMappingMode.OPEN_INTEREST,
                                  contract_depth_offset=0, extended_market_hours=False)
        self.nq.set_filter(0, 180)
        self.agg = {}
        self.day = None
        self._new_day()

    def _new_day(self):
        self.pv = self.vv = 0.0
        self.bb = self.bs = 0.0          # aggressive buy / sell of the current 5-min bar
        self.prev_inside = None
        self.last = None
        self.side = 0
        self.done = False
        self.tr = None                   # open trade dict

    def _add(self, key, x):
        a = self.agg.setdefault(key, [0, 0.0, 0.0, 0])
        a[0] += 1; a[1] += x; a[2] += x * x; a[3] += 1 if x > 0 else 0

    def _close(self, x):
        y = self.day.year
        for g in self.tr["g"]:
            self._add((y, g), x)
        self._add((y, "all"), x)
        self.tr = None

    def on_data(self, data: Slice):
        t = self.time
        if self.day != t.date():
            if self.tr is not None and self.last is not None:
                self._close(self.tr["d"] * (self.last - self.tr["e"]))
            self.day = t.date()
            self._new_day()
        bar = data.bars.get(self.nq.symbol)
        if bar is None:
            return
        secs = t.hour * 3600 + t.minute * 60 + t.second - (9 * 3600 + 30 * 60)
        if secs <= 0 or secs > 23400:
            return
        hm = t.hour * 60 + t.minute
        c, h, l, v = float(bar.close), float(bar.high), float(bar.low), float(bar.volume)
        if self.tr is not None:
            d, e = self.tr["d"], self.tr["e"]
            if (d == 1 and l <= e - STOP_PT) or (d == -1 and h >= e + STOP_PT):
                self._close(-STOP_PT)
            elif (d == 1 and h >= e + TGT_PT) or (d == -1 and l <= e - TGT_PT):
                self._close(TGT_PT)
            elif hm >= EOD:
                self._close(d * (c - e))
        if v > 0:
            q = data.quote_bars.get(self.nq.symbol)
            sd = 0
            if q is not None and q.bid is not None and q.ask is not None and q.bid.close > 0 and q.ask.close > 0:
                mid = (float(q.bid.close) + float(q.ask.close)) / 2.0
                sd = 1 if c > mid else (-1 if c < mid else 0)
            if sd == 0 and self.last is not None:
                sd = 1 if c > self.last else (-1 if c < self.last else self.side)
            if sd > 0:
                self.bb += v
            elif sd < 0:
                self.bs += v
            self.side = sd or self.side
            self.pv += (h + l + c) / 3.0 * v
            self.vv += v
        self.last = c
        if secs % 300 == 0:                                  # 5-min bar close
            if self.vv > 0 and hm < EOD:
                vw = self.pv / self.vv
                up, dn = vw * 1.002, vw * 0.998
                inside = dn <= c <= up
                if (not self.done and self.prev_inside and not inside and self.tr is None
                        and t.weekday() != 2 and hm >= 9 * 60 + 40):
                    d = 1 if c > up else -1
                    tot = self.bb + self.bs
                    imb = d * (self.bb - self.bs) / tot if tot > 0 else 0.0
                    g = ["pos" if imb > 0 else "neg"]
                    if imb >= 0.05:
                        g.append("c05")
                    if imb <= -0.05:
                        g.append("a05")
                    self.tr = {"d": d, "e": c, "g": g}
                    self.done = True
                self.prev_inside = inside
            self.bb = self.bs = 0.0

    def on_end_of_algorithm(self):
        for (y, g), (n, s1, s2, w) in sorted(self.agg.items()):
            if n < 2:
                continue
            m = s1 / n
            var = max(0.0, s2 / n - m * m)
            tt = m / math.sqrt(var / n) if var > 0 else 0.0
            self.set_runtime_statistic(f"{y} VG {g}", f"{m:+.1f}pt/{tt:+.1f}/{n} wins {w}")
