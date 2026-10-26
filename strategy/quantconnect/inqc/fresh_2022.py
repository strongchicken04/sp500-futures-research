# region imports
from AlgorithmImports import *
from collections import deque
import math
# endregion
#
# FRESH ORDER-FLOW / LIQUIDITY IDEAS, computed INSIDE QuantConnect (day shift
# 2026-10-26, rules fixed before results). Exports no market data: only
# aggregate statistics per year as runtime statistics.
#
# Per 1-second bar of NQ and ES (RTH): aggressor side = trade close vs quote
# mid (tick rule at the mid); per minute: aggressive buy / sell volume, mean
# spread, mean top-of-book size imbalance (bid size - ask size) / (sum), last
# trade price. Events on minutes ending 10:01 .. 15:31 ET, first per day per
# idea, forward return in the event direction from the minute's last NQ trade:
#   F1 SPREAD   NQ minute mean spread >= 3 x its 20-day mean for that minute;
#               direction = the minute's NQ price change (continuation test);
#               also reports the 15-min absolute move vs its 20-day mean.
#   F2 BOOK     NQ minute mean book imbalance >= +0.5 -> long, <= -0.5 -> short
#   F3 ABSORB   NQ aggressive buy >= 2 x its 20-day mean and >= 2 x sell, but
#               the minute closes at or below the previous minute -> SHORT
#               (passive seller absorbed the buyers); mirror -> LONG
#   F5 ESLEAD   ES aggressive side >= 3 x its 20-day mean and >= 2 x the other
#               side while NQ moved < 0.02% in that minute -> NQ in ES direction
#   F6 OPEN30   D = (buy - sell) / (buy + sell) of NQ 09:30-10:00; |D| >= 0.05
#               -> direction sign(D), entry at 10:00, returns to 12:00 / 15:55
# Added after the Jan-Mar 2024 pilot (thresholds too rare, stated openly):
#   F6b |D| >= 0.02; F2b book imbalance >= 0.3; F2N = days with book sizes.
# Horizons 1 / 5 / 15 / 30 min (F6: 120 min and 15:55). Gross bp, averaged per
# day (one event per idea per day), mean / t / days per year.

START = (2021, 12, 1)   # December = 20-day warm-up
END = (2022, 12, 31)
M_FIRST, M_LAST, M_EOD = 30, 360, 385
HORIZ = (1, 5, 15, 30)


class FreshInQC(QCAlgorithm):

    def initialize(self):
        self.set_start_date(*START)
        self.set_end_date(*END)
        self.set_cash(1_000_000)
        kw = dict(data_normalization_mode=DataNormalizationMode.RAW,
                  data_mapping_mode=DataMappingMode.OPEN_INTEREST,
                  contract_depth_offset=0, extended_market_hours=False)
        self.nq = self.add_future(Futures.Indices.NASDAQ_100_E_MINI, Resolution.SECOND, **kw)
        self.es = self.add_future(Futures.Indices.SP_500_E_MINI, Resolution.SECOND, **kw)
        self.nq.set_filter(0, 180)
        self.es.set_filter(0, 180)
        self.hist = {k: [deque(maxlen=20) for _ in range(390)] for k in ("nqb", "nqs", "esb", "ess", "spr")}
        self.agg = {}
        self.day = None
        self._new_day()

    def _new_day(self):
        z = lambda: [0.0] * 390
        self.m = {k: z() for k in ("nqb", "nqs", "esb", "ess", "spr", "sprn", "imb", "imbn")}
        self.px = [None] * 390
        self.last = {"nq": None, "es": None}
        self.side = {"nq": 0, "es": 0}
        self.events = {}            # idea -> (minute, dir)
        self.open30 = None
        self.book_seen = False

    def _side(self, key, c, q):
        s = 0
        if q is not None and q.bid is not None and q.ask is not None and q.bid.close > 0 and q.ask.close > 0:
            mid = (float(q.bid.close) + float(q.ask.close)) / 2.0
            s = 1 if c > mid else (-1 if c < mid else 0)
        if s == 0 and self.last[key] is not None:
            s = 1 if c > self.last[key] else (-1 if c < self.last[key] else self.side[key])
        self.side[key] = s or self.side[key]
        self.last[key] = c
        return s

    def on_data(self, data: Slice):
        t = self.time
        if self.day != t.date():
            self._close_day()
            self.day = t.date()
            self._new_day()
        secs = t.hour * 3600 + t.minute * 60 + t.second - (9 * 3600 + 30 * 60)
        if secs <= 0 or secs > 23400:
            return
        m = (secs - 1) // 60
        for key, fut in (("nq", self.nq), ("es", self.es)):
            bar = data.bars.get(fut.symbol)
            q = data.quote_bars.get(fut.symbol)
            if key == "nq" and q is not None and q.bid is not None and q.ask is not None and q.bid.close > 0 and q.ask.close > 0:
                self.m["spr"][m] += float(q.ask.close) - float(q.bid.close)
                self.m["sprn"][m] += 1
                bs, az = float(q.last_bid_size), float(q.last_ask_size)
                if bs + az > 0:
                    self.m["imb"][m] += (bs - az) / (bs + az)
                    self.m["imbn"][m] += 1
            if bar is None or bar.volume <= 0:
                continue
            c, v = float(bar.close), float(bar.volume)
            s = self._side(key, c, q)
            if s > 0:
                self.m[key + "b"][m] += v
            elif s < 0:
                self.m[key + "s"][m] += v
            if key == "nq":
                self.px[m] = c
        if secs % 60 == 0 and M_FIRST <= m <= M_LAST:
            self._check(m)

    def _mean(self, k, m):
        h = self.hist[k][m]
        return sum(h) / len(h) if len(h) == 20 else None

    def _check(self, m):
        ev = self.events
        p, p0 = self.px[m], self.px[m - 1]
        if p is None or p0 is None:
            return
        if m == M_FIRST and self.open30 is None:
            b = sum(self.m["nqb"][:30]); s = sum(self.m["nqs"][:30])
            if b + s > 0:
                dd = (b - s) / (b + s)
                if abs(dd) >= 0.05:
                    ev["F6 OPEN30"] = (m, 1 if dd > 0 else -1)
                if abs(dd) >= 0.02:
                    ev["F6b OPEN30"] = (m, 1 if dd > 0 else -1)
            self.open30 = True
        n = self.m["sprn"][m]
        ms = self._mean("spr", m)
        if "F1 SPREAD" not in ev and n > 0 and ms and self.m["spr"][m] / n >= 3 * ms and p != p0:
            ev["F1 SPREAD"] = (m, 1 if p > p0 else -1)
        ni = self.m["imbn"][m]
        if ni > 0:
            self.book_seen = True
            im = self.m["imb"][m] / ni
            if "F2 BOOK" not in ev and abs(im) >= 0.5:
                ev["F2 BOOK"] = (m, 1 if im > 0 else -1)
            if "F2b BOOK" not in ev and abs(im) >= 0.3:
                ev["F2b BOOK"] = (m, 1 if im > 0 else -1)
        b, s = self.m["nqb"][m], self.m["nqs"][m]
        mb, msl = self._mean("nqb", m), self._mean("nqs", m)
        if "F3 ABSORB" not in ev and mb and msl:
            if b >= 2 * mb and b >= 2 * s and p <= p0:
                ev["F3 ABSORB"] = (m, -1)
            elif s >= 2 * msl and s >= 2 * b and p >= p0:
                ev["F3 ABSORB"] = (m, 1)
        eb, es_ = self.m["esb"][m], self.m["ess"][m]
        meb, mes = self._mean("esb", m), self._mean("ess", m)
        if "F5 ESLEAD" not in ev and meb and mes and abs(p / p0 - 1) < 0.0002:
            if eb >= 3 * meb and eb >= 2 * es_:
                ev["F5 ESLEAD"] = (m, 1)
            elif es_ >= 3 * mes and es_ >= 2 * eb:
                ev["F5 ESLEAD"] = (m, -1)

    def _ret(self, m, d, j):
        j = min(M_EOD, j)
        p1 = next((self.px[x] for x in range(j, m, -1) if self.px[x] is not None), None)
        return None if p1 is None else d * (p1 / self.px[m] - 1.0) * 1e4

    def _add(self, key, x):
        a = self.agg.setdefault(key, [0, 0.0, 0.0])
        a[0] += 1; a[1] += x; a[2] += x * x

    def _close_day(self):
        if self.day is None:
            return
        y = self.day.year
        for idea, (m, d) in self.events.items():
            f6 = idea.startswith("F6")
            hs = ((120, M_FIRST + 120), (999, M_EOD)) if f6 else tuple((h, m + h) for h in HORIZ)
            for h, j in hs:
                r = self._ret(m, d, j)
                if r is not None:
                    self._add((y, idea, h), r)
            if idea == "F1 SPREAD":
                r = self._ret(m, 1, m + 15)
                if r is not None:
                    self._add((y, "F1 ABSMOVE", 15), abs(r))
        self.f2n = getattr(self, "f2n", 0) + (1 if self.book_seen else 0)
        for k in ("nqb", "nqs", "esb", "ess"):
            for mm in range(390):
                self.hist[k][mm].append(self.m[k][mm])
        for mm in range(390):
            if self.m["sprn"][mm] > 0:
                self.hist["spr"][mm].append(self.m["spr"][mm] / self.m["sprn"][mm])

    def on_end_of_algorithm(self):
        self._close_day()
        out = {}
        for (y, idea, h), (n, s1, s2) in sorted(self.agg.items()):
            if n < 2:
                continue
            mm = s1 / n
            var = max(0.0, s2 / n - mm * mm)
            tt = mm / math.sqrt(var / n) if var > 0 else 0.0
            out.setdefault(f"{y} {idea}", []).append(f"{h}m {mm:+.1f}/{tt:+.1f}/{n}")
        for k, parts in out.items():
            self.set_runtime_statistic(k, " ".join(parts))
        self.set_runtime_statistic("F2N days with book sizes", str(getattr(self, "f2n", 0)))
