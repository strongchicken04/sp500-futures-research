# region imports
from AlgorithmImports import *
import math
# endregion
#
# LATE-SESSION REAL ORDER FLOW -> LAST HOUR, computed INSIDE QuantConnect
# (night 2026-10-27/28, rules fixed before results). Exports no market data:
# only aggregate statistics per year as runtime statistics.
#
# Aggressive side per 1-second bar: trade close vs quote mid, tick rule at the
# mid (as rs_delta_inqc / vg_flow_inqc). RTH only.
#   D   = (buy - sell) / (buy + sell) of aggressive volume 09:30 -> 15:00
#   M   = sign of the move open -> 15:00 close
#   R60 = 15:00 close -> 16:00 close (gross bp)
#   d50 = imbalance 15:00 -> 15:50, R10 = 15:50 close -> 16:00 close
#   strong = close > open and range position > 0.77 at 15:00 (late-day long
#   rules 3-4, qqq_late_long.py); weak = mirror (close < open, < 0.23)
# Groups (signed trade return, gross bp; mean / t / n / wins per year):
#   ALL   R60 x M (late momentum baseline)
#   AGR   |D| >= 0.05 and sign D = M: R60 x M
#   DIV   |D| >= 0.05 and sign D != M: R60 x M
#   FLW   |D| >= 0.05: R60 x sign D (follow the day's flow)
#   STR+  strong and D >= +0.05: long R60;  STR-  strong and D <= -0.05: long R60
#   WK-   weak and D <= -0.05: short R60;   WK+   weak and D >= +0.05: short R60
#   C10   |d50| >= 0.05: R10 x sign d50 (closing-imbalance proxy)
# v2 (after 2024 gave NO day with |D| >= 0.05 and only 48 with |d50| >= 0.05 -
# a whole-day imbalance is much smaller than a 5-min one; stated openly): the
# threshold is TH = 0.02 for every group above, plus sign-only groups
#   AGRs / DIVs (D x M > 0 / < 0), STRs+ / STRs- (strong and D > 0 / <= 0),
#   C10s (sign of d50, any size).

TH = 0.02
START = (2023, 1, 1)
END = (2023, 12, 31)


class LateFlowInQC(QCAlgorithm):

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
        self.op = None
        self.hi = -1e18
        self.lo = 1e18
        self.b = self.s = 0.0           # 09:30 -> 15:00
        self.b2 = self.s2 = 0.0         # 15:00 -> 15:50
        self.last = None
        self.side = 0
        self.c15 = self.c1550 = None
        self.snap = None                # (D, M, strong, weak) at 15:00

    def _add(self, key, x):
        a = self.agg.setdefault(key, [0, 0.0, 0.0, 0])
        a[0] += 1; a[1] += x; a[2] += x * x; a[3] += 1 if x > 0 else 0

    def _close_day(self):
        if self.day is None or self.snap is None or self.last is None or self.c15 is None:
            return
        y = self.day.year
        D, M, strong, weak = self.snap
        r60 = (self.last / self.c15 - 1.0) * 1e4
        if M != 0:
            self._add((y, "ALL"), r60 * M)
            if abs(D) >= TH:
                self._add((y, "AGR" if D * M > 0 else "DIV"), r60 * M)
            self._add((y, "AGRs" if D * M > 0 else "DIVs"), r60 * M)
        if abs(D) >= TH:
            self._add((y, "FLW"), r60 * (1 if D > 0 else -1))
        if strong:
            self._add((y, "STRs+" if D > 0 else "STRs-"), r60)
        if strong and D >= TH:
            self._add((y, "STR+"), r60)
        if strong and D <= -TH:
            self._add((y, "STR-"), r60)
        if weak and D <= -TH:
            self._add((y, "WK-"), -r60)
        if weak and D >= TH:
            self._add((y, "WK+"), -r60)
        tot2 = self.b2 + self.s2
        if self.c1550 is not None and tot2 > 0:
            d50 = (self.b2 - self.s2) / tot2
            r10 = (self.last / self.c1550 - 1.0) * 1e4
            if abs(d50) >= TH:
                self._add((y, "C10"), r10 * (1 if d50 > 0 else -1))
            if d50 != 0:
                self._add((y, "C10s"), r10 * (1 if d50 > 0 else -1))

    def on_data(self, data: Slice):
        t = self.time
        if self.day != t.date():
            self._close_day()
            self.day = t.date()
            self._new_day()
        bar = data.bars.get(self.nq.symbol)
        if bar is None:
            return
        secs = t.hour * 3600 + t.minute * 60 + t.second - (9 * 3600 + 30 * 60)
        if secs <= 0 or secs > 23400:
            return
        c, h, l, v = float(bar.close), float(bar.high), float(bar.low), float(bar.volume)
        if self.op is None:
            self.op = float(bar.open)
        if v > 0:
            q = data.quote_bars.get(self.nq.symbol)
            sd = 0
            if q is not None and q.bid is not None and q.ask is not None and q.bid.close > 0 and q.ask.close > 0:
                mid = (float(q.bid.close) + float(q.ask.close)) / 2.0
                sd = 1 if c > mid else (-1 if c < mid else 0)
            if sd == 0 and self.last is not None:
                sd = 1 if c > self.last else (-1 if c < self.last else self.side)
            if secs <= 19800:
                if sd > 0:
                    self.b += v
                elif sd < 0:
                    self.s += v
            elif secs <= 22800:
                if sd > 0:
                    self.b2 += v
                elif sd < 0:
                    self.s2 += v
            self.side = sd or self.side
        if secs <= 19800:
            self.hi = max(self.hi, h)
            self.lo = min(self.lo, l)
        self.last = c
        if secs == 19800 or (self.snap is None and secs > 19800):     # 15:00 snapshot
            self.c15 = c
            tot = self.b + self.s
            D = (self.b - self.s) / tot if tot > 0 else 0.0
            M = 1 if c > self.op else (-1 if c < self.op else 0)
            rp = (c - self.lo) / (self.hi - self.lo) if self.hi > self.lo else 0.5
            self.snap = (D, M, M == 1 and rp > 0.77, M == -1 and rp < 0.23)
        if self.c1550 is None and secs >= 22800:
            self.c1550 = c

    def on_end_of_algorithm(self):
        self._close_day()
        for (y, g), (n, s1, s2, w) in sorted(self.agg.items()):
            if n < 2:
                continue
            m = s1 / n
            var = max(0.0, s2 / n - m * m)
            tt = m / math.sqrt(var / n) if var > 0 else 0.0
            self.set_runtime_statistic(f"{y} LF {g}", f"{m:+.1f}bp/{tt:+.1f}/{n} wins {w}")
