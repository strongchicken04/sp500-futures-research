# region imports
from AlgorithmImports import *
from collections import deque
import math
# endregion
#
# F3 ABSORPTION x LOCATION, computed INSIDE QuantConnect (night 2026-10-27/28,
# rules fixed before results). Exports no market data: only aggregate
# statistics per year as runtime statistics.
#
# Event = the F3 main cell (f3_trade_inqc.py): NQ minute ending 10:01..15:31 ET
# with aggressive buy >= 2 x its 20-day mean and >= 2 x sell, closing at or
# below the previous minute -> LONG (follow the aggressors); mirror -> SHORT.
# ALL events of the day (not only the first), one open trade at a time.
# Entry at the minute's last trade, stop 0.25% (1-second highs / lows), exit
# after 15 min (capped at 15:55).
# Location of the event minute's close (fixed before results):
#   LOW   within 0.10% of the running RTH day low or the previous RTH low
#   HIGH  within 0.10% of the running RTH day high or the previous RTH high
#   MID   neither (if both, counted in both)
# Groups: L/S x LOW/HIGH/MID and ALL; gross bp mean / t / n / stop-outs.

START = (2023, 1, 1)
END = (2023, 12, 31)
M_FIRST, M_LAST, M_EOD = 30, 360, 385
STOP = 0.0025
HOLDS = (15,)
NEAR = 0.0010


class F3LevelInQC(QCAlgorithm):

    def initialize(self):
        self.set_start_date(*START)
        self.set_end_date(*END)
        self.set_cash(1_000_000)
        self.nq = self.add_future(Futures.Indices.NASDAQ_100_E_MINI, Resolution.SECOND,
                                  data_normalization_mode=DataNormalizationMode.RAW,
                                  data_mapping_mode=DataMappingMode.OPEN_INTEREST,
                                  contract_depth_offset=0, extended_market_hours=False)
        self.nq.set_filter(0, 180)
        self.hb = [deque(maxlen=20) for _ in range(390)]
        self.hs = [deque(maxlen=20) for _ in range(390)]
        self.agg = {}
        self.pdh = self.pdl = None
        self.day = None
        self._new_day()

    def _new_day(self):
        self.b = [0.0] * 390
        self.s = [0.0] * 390
        self.px = [None] * 390
        self.last = None
        self.side = 0
        self.trades = []          # dicts: d, e, m, hold, done, g
        self.dhi = self.dlo = None

    def _close_day(self):
        if self.day is None:
            return
        if self.dhi is not None:
            self.pdh, self.pdl = self.dhi, self.dlo
        for mm in range(390):
            if self.px[mm] is not None:
                self.hb[mm].append(self.b[mm])
                self.hs[mm].append(self.s[mm])

    def _add(self, key, x, stopped):
        a = self.agg.setdefault(key, [0, 0.0, 0.0, 0])
        a[0] += 1; a[1] += x; a[2] += x * x; a[3] += 1 if stopped else 0

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
        m = (secs - 1) // 60
        c, h, l, v = float(bar.close), float(bar.high), float(bar.low), float(bar.volume)
        for tr in self.trades:
            if tr["done"]:
                continue
            d, e = tr["d"], tr["e"]
            stop = e * (1 - d * STOP)
            if (d == 1 and l <= stop) or (d == -1 and h >= stop):
                for g in tr["g"]:
                    self._add((self.day.year, g), -STOP * 1e4, True)
                tr["done"] = True
            elif m >= min(M_EOD, tr["m"] + tr["hold"]):
                for g in tr["g"]:
                    self._add((self.day.year, g), d * (c / e - 1.0) * 1e4, False)
                tr["done"] = True
        if v > 0:
            q = data.quote_bars.get(self.nq.symbol)
            sd = 0
            if q is not None and q.bid is not None and q.ask is not None and q.bid.close > 0 and q.ask.close > 0:
                mid = (float(q.bid.close) + float(q.ask.close)) / 2.0
                sd = 1 if c > mid else (-1 if c < mid else 0)
            if sd == 0 and self.last is not None:
                sd = 1 if c > self.last else (-1 if c < self.last else self.side)
            if sd > 0:
                self.b[m] += v
            elif sd < 0:
                self.s[m] += v
            self.side = sd or self.side
            self.last = c
            self.px[m] = c
        if self.dhi is None:
            self.dhi, self.dlo = h, l
        else:
            self.dhi, self.dlo = max(self.dhi, h), min(self.dlo, l)
        if secs % 60 == 0 and M_FIRST <= m <= M_LAST and not any(not x["done"] for x in self.trades):
            p, p0 = self.px[m], self.px[m - 1]
            hb, hs = self.hb[m], self.hs[m]
            if p is None or p0 is None or len(hb) < 20:
                return
            mb, ms = sum(hb) / 20.0, sum(hs) / 20.0
            b, s = self.b[m], self.s[m]
            d = 0
            if mb > 0 and b >= 2 * mb and b >= 2 * s and p <= p0:
                d = 1
            elif ms > 0 and s >= 2 * ms and s >= 2 * b and p >= p0:
                d = -1
            if d and self.dhi is not None:
                side = "L" if d == 1 else "S"
                lows = [x for x in (self.dlo, self.pdl) if x is not None]
                highs = [x for x in (self.dhi, self.pdh) if x is not None]
                g = ["ALL"]
                near_lo = any(abs(p / x - 1.0) <= NEAR for x in lows)
                near_hi = any(abs(p / x - 1.0) <= NEAR for x in highs)
                if near_lo:
                    g.append(side + "_LOW")
                if near_hi:
                    g.append(side + "_HIGH")
                if not near_lo and not near_hi:
                    g.append(side + "_MID")
                for hold in HOLDS:
                    self.trades.append({"d": d, "e": p, "m": m, "hold": hold, "done": False, "g": g})

    def on_end_of_algorithm(self):
        for (y, hold), (n, s1, s2, k) in sorted(self.agg.items()):
            if n < 2:
                continue
            mm = s1 / n
            var = max(0.0, s2 / n - mm * mm)
            tt = mm / math.sqrt(var / n) if var > 0 else 0.0
            self.set_runtime_statistic(f"{y} F3L {hold}", f"{mm:+.1f}/{tt:+.1f}/{n} stops {k}")
