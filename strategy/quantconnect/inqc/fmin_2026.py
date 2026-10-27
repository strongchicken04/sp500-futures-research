# region imports
from AlgorithmImports import *
import math
# endregion
#
# FIRST-MINUTE REAL ORDER FLOW -> 09:31 SPRINT DIRECTION, computed INSIDE
# QuantConnect (night 2026-10-27/28, rules fixed before results). Exports no
# market data: only aggregate statistics per year as runtime statistics.
#
# The 09:31 evaluation sprint (Lucid 7) has no directional edge from price or
# the 50-day trend. Can the aggressive flow of the first minute give one?
# I1 = (buy - sell) / (buy + sell) of aggressive volume 09:30:00 -> 09:31:00
# (trade close vs quote mid, tick rule at the mid, as the other in-QC studies).
# Entry at the 09:31:00 close in direction sign(I1); bracket target 0.25% /
# stop 0.40% (Lucid 7 shape), first touch on 1-second highs / lows from the
# next second, stop first if both; unresolved -> flat 15:55.
# Groups (per year): FLOW (sign I1, any size), F10 (|I1| >= 0.10), F20
# (|I1| >= 0.20), PX (sign of the first-minute price move, baseline), AGREE /
# CLASH (flow and price move agree / disagree, trade the FLOW side).
# Output per group: resolved wins / resolved n (random-walk rate 0.40 / 0.65 =
# 61.5%), mean gross bp of all trades incl. unresolved, n.

START = (2026, 1, 1)
END = (2026, 7, 28)
TGT, STP = 0.0025, 0.0040


class FirstMinuteInQC(QCAlgorithm):

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
        self.b = self.s = 0.0
        self.last = None
        self.side = 0
        self.trades = []                 # dicts: g (groups), d, e, done
        self.fired = False

    def _add(self, g, res, x):
        a = self.agg.setdefault((self.day.year, g), [0, 0, 0, 0.0, 0.0])
        a[0] += 1                        # n
        a[1] += 1 if res == 1 else 0     # resolved wins
        a[2] += 1 if res != 0 else 0     # resolved
        a[3] += x; a[4] += x * x

    def _finish(self, tr, res, x):
        for g in tr["g"]:
            self._add(g, res, x)
        tr["done"] = True

    def _close_day(self):
        if self.day is None or self.last is None:
            return
        for tr in self.trades:
            if not tr["done"]:
                self._finish(tr, 0, tr["d"] * (self.last / tr["e"] - 1.0) * 1e4)

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
        if secs <= 0 or secs > 23100:                     # RTH up to 15:55
            return
        c, h, l, v = float(bar.close), float(bar.high), float(bar.low), float(bar.volume)
        if self.op is None:
            self.op = float(bar.open)
        for tr in self.trades:
            if tr["done"]:
                continue
            d, e = tr["d"], tr["e"]
            if (d == 1 and l <= e * (1 - STP)) or (d == -1 and h >= e * (1 + STP)):
                self._finish(tr, -1, -STP * 1e4)
            elif (d == 1 and h >= e * (1 + TGT)) or (d == -1 and l <= e * (1 - TGT)):
                self._finish(tr, 1, TGT * 1e4)
        if v > 0 and secs <= 60:
            q = data.quote_bars.get(self.nq.symbol)
            sd = 0
            if q is not None and q.bid is not None and q.ask is not None and q.bid.close > 0 and q.ask.close > 0:
                mid = (float(q.bid.close) + float(q.ask.close)) / 2.0
                sd = 1 if c > mid else (-1 if c < mid else 0)
            if sd == 0 and self.last is not None:
                sd = 1 if c > self.last else (-1 if c < self.last else self.side)
            if sd > 0:
                self.b += v
            elif sd < 0:
                self.s += v
            self.side = sd or self.side
        self.last = c
        if not self.fired and 60 <= secs < 120:          # 09:31:00 (or the first bar after it)
            self.fired = True
            tot = self.b + self.s
            if tot <= 0:
                return
            I1 = (self.b - self.s) / tot
            px = 1 if c > self.op else (-1 if c < self.op else 0)
            fd = 1 if I1 > 0 else (-1 if I1 < 0 else 0)
            if fd != 0:
                g = ["FLOW"]
                if abs(I1) >= 0.10:
                    g.append("F10")
                if abs(I1) >= 0.20:
                    g.append("F20")
                if px != 0:
                    g.append("AGREE" if px == fd else "CLASH")
                self.trades.append({"g": g, "d": fd, "e": c, "done": False})
            if px != 0:
                self.trades.append({"g": ["PX"], "d": px, "e": c, "done": False})

    def on_end_of_algorithm(self):
        self._close_day()
        for (y, g), (n, w, r, s1, s2) in sorted(self.agg.items()):
            if n < 2:
                continue
            m = s1 / n
            var = max(0.0, s2 / n - m * m)
            tt = m / math.sqrt(var / n) if var > 0 else 0.0
            self.set_runtime_statistic(f"{y} FM {g}", f"win {w}/{r} {m:+.1f}bp/{tt:+.1f}/{n}")
