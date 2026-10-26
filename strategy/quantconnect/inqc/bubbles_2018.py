# region imports
from AlgorithmImports import *
from collections import deque
import math
# endregion
#
# BIG-TRADES BUBBLES, computed INSIDE QuantConnect (owner 2026-10-26).
# This algorithm exports no market data: it only computes aggregate research
# statistics (means, t-stats and counts of forward returns per variant and
# year) and reports them as a handful of runtime statistics.
#
# Aggressor side per one-second bar: trade close above the quote mid = buy,
# below = sell, at the mid = same side as the previous price change (tick
# rule). Per RTH minute: aggressive buy / sell volume.
# Bubble at the end of minute m (10:00 .. 15:30 ET): buy volume >= R x the
# 20-day mean buy volume of that minute AND buy >= 2 x sell -> BUY bubble;
# mirror -> SELL bubble. R = 2 / 3.
# Filters: all | with the trend since 09:30 AND the VWAP side ("both") |
# against the trend since 09:30 ("against").
# Forward return WITH the bubble from the minute's last trade price after
# 1 / 2 / 5 / 15 / 30 / 60 min (capped at 15:55), gross bp, averaged per day first
# (day-clustered), then mean / t / days per year bucket.

START = (2017, 12, 1)   # December = 20-day warm-up
END = (2018, 12, 31)
RS = (2, 3)
HORIZ = (1, 2, 5, 15, 30, 60)
FILTERS = ("all", "both", "against")
M_FIRST, M_LAST = 30, 360          # minute index 30 = minute ending 10:01; 360 = 15:31
M_EOD = 385                        # minute ending 15:56


class BubblesInQC(QCAlgorithm):

    def initialize(self):
        self.set_start_date(*START)
        self.set_end_date(*END)
        self.set_cash(1_000_000)
        self.fut = self.add_future(Futures.Indices.NASDAQ_100_E_MINI, Resolution.SECOND,
                                   data_normalization_mode=DataNormalizationMode.RAW,
                                   data_mapping_mode=DataMappingMode.OPEN_INTEREST,
                                   contract_depth_offset=0, extended_market_hours=False)
        self.fut.set_filter(0, 180)
        self.hist_buy = [deque(maxlen=20) for _ in range(390)]
        self.hist_sell = [deque(maxlen=20) for _ in range(390)]
        self.agg = {}                 # (year, R, filter, h) -> [n_days, sum, sumsq]
        self.day = None
        self._new_day()

    def _new_day(self):
        self.buy = [0.0] * 390
        self.sell = [0.0] * 390
        self.px = [None] * 390        # last trade price per minute
        self.open = None
        self.pv = self.vv = 0.0
        self.vwap_end = [None] * 390
        self.last_px = None
        self.last_side = 0
        self.events = []              # (minute, dir, R, filter)

    def _close_day(self):
        if self.day is None:
            return
        per = {}
        for m, d, r, f in self.events:
            p0 = self.px[m]
            if p0 is None:
                continue
            for h in HORIZ:
                j = min(M_EOD, m + h)
                p1 = next((self.px[x] for x in range(j, m, -1) if self.px[x] is not None), None)
                if p1 is None:
                    continue
                per.setdefault((r, f, h), []).append(d * (p1 / p0 - 1.0) * 1e4)
        y = self.day.year
        for (r, f, h), v in per.items():
            a = self.agg.setdefault((y, r, f, h), [0, 0.0, 0.0])
            x = sum(v) / len(v)
            a[0] += 1
            a[1] += x
            a[2] += x * x
        for m in range(390):
            if self.px[m] is not None:
                self.hist_buy[m].append(self.buy[m])
                self.hist_sell[m].append(self.sell[m])

    def on_data(self, data: Slice):
        t = self.time
        if self.day != t.date():
            self._close_day()
            self.day = t.date()
            self._new_day()
        bar = data.bars.get(self.fut.symbol)
        if bar is None or bar.volume <= 0:
            return
        secs = (t.hour * 3600 + t.minute * 60 + t.second) - (9 * 3600 + 30 * 60)
        if secs <= 0 or secs > 23400:
            return
        m = (secs - 1) // 60
        c = float(bar.close)
        v = float(bar.volume)
        q = data.quote_bars.get(self.fut.symbol)
        side = 0
        if q is not None and q.bid is not None and q.ask is not None and q.bid.close > 0 and q.ask.close > 0:
            mid = (float(q.bid.close) + float(q.ask.close)) / 2.0
            side = 1 if c > mid else (-1 if c < mid else 0)
        if side == 0 and self.last_px is not None:
            side = 1 if c > self.last_px else (-1 if c < self.last_px else self.last_side)
        if side > 0:
            self.buy[m] += v
        elif side < 0:
            self.sell[m] += v
        self.last_side = side or self.last_side
        self.last_px = c
        if self.open is None:
            self.open = float(bar.open)
        self.pv += (float(bar.high) + float(bar.low) + c) / 3.0 * v
        self.vv += v
        self.px[m] = c
        self.vwap_end[m] = self.pv / self.vv
        if secs % 60 == 0 and M_FIRST <= m <= M_LAST:
            self._check(m, c)

    def _check(self, m, c):
        hb, hs = self.hist_buy[m], self.hist_sell[m]
        if len(hb) < 20:
            return
        mb, ms = sum(hb) / 20.0, sum(hs) / 20.0
        b, s = self.buy[m], self.sell[m]
        for r in RS:
            d = 0
            if mb > 0 and b >= r * mb and b >= 2.0 * s:
                d = 1
            elif ms > 0 and s >= r * ms and s >= 2.0 * b:
                d = -1
            if d == 0:
                continue
            trend = d * (c / self.open - 1.0) > 0
            vw = d * (c - self.vwap_end[m]) > 0
            self.events.append((m, d, r, "all"))
            if trend and vw:
                self.events.append((m, d, r, "both"))
            if not trend:
                self.events.append((m, d, r, "against"))

    def on_end_of_algorithm(self):
        self._close_day()
        rows = []
        for (y, r, f, h), (n, s1, s2) in sorted(self.agg.items()):
            if n < 2:
                continue
            mean = s1 / n
            var = max(0.0, s2 / n - mean * mean)
            tt = mean / math.sqrt(var / n) if var > 0 else 0.0
            rows.append(((y, r, f), f"{h}m {mean:+.1f}/{tt:+.1f}/{n}"))
        keys = {}
        for k, txt in rows:
            keys.setdefault(k, []).append(txt)
        for (y, r, f), parts in keys.items():
            self.set_runtime_statistic(f"{y} R{r} {f}", " ".join(parts))
        self.log(f"keys {len(keys)}")
