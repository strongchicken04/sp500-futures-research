# region imports
from AlgorithmImports import *
# endregion
#
# NOISE-AREA MOMENTUM + TIME-OF-DAY PATH EXPORTER (NQ, 2018-2025)
#
#   Z  Zarattini, Aziz & Barbon (2024) "Beat the Market" as published, on NQ:
#      sigma_t = mean of |close_t / open - 1| at that minute over the last 14
#      sessions; upper band = max(open, prior close) x (1 + sigma_t), lower
#      band = min(open, prior close) x (1 - sigma_t). Decisions only at :00
#      and :30 from 10:00: long above the upper band, short below the lower;
#      a long exits when price is below max(upper band, VWAP), a short when
#      above min(lower band, VWAP); a signal the other way reverses. Flat at
#      15:55. Each trade also records first-touch minutes for LEVELS bp both
#      ways, so profit-target variants can be scored offline.
#   P  One tag per day with the prior close and the price at every half hour
#      from 09:30 to 15:30 plus 15:55, and the high and low of every half
#      hour, for time-of-day tests (lunch effect, etc.).
#
# Tag Z: Z,<yyyymmdd>,<side>,<entry hhmm>,<entry px>,<exit hhmm>,<exit px>,
#          <sigma bp>,<up x13>,<dn x13>
# Tag P: P,<yyyymmdd>,<dow>,<prior close>,<px x14>,<hi x13>,<lo x13>

LEVELS = [5, 10, 15, 20, 25, 30, 40, 50, 60, 75, 100, 125, 150]
EOD = 15 * 60 + 55
CHECKS = [9 * 60 + 30 + 30 * i for i in range(13)] + [EOD]   # 09:30 .. 15:30, 15:55


class NoiseTodExporter(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2018, 1, 1)
        self.SetEndDate(2025, 12, 31)
        self.SetCash(1_000_000)
        self.n_tags = 0
        self.fut = self.AddFuture(
            Futures.Indices.NASDAQ_100_E_MINI, Resolution.Minute,
            dataNormalizationMode=DataNormalizationMode.Raw,
            dataMappingMode=DataMappingMode.OpenInterest,
            contractDepthOffset=0, extendedMarketHours=True)
        self.fut.SetFilter(0, 180)
        self.day = None
        self.pc = None
        self.noise = {}
        self._reset()

    def _reset(self):
        self.o930 = None
        self.pv = self.vol = 0.0
        self.pos = None
        self.px = {}
        self.hi = [None] * 13
        self.lo = [None] * 13

    def OnData(self, slice):
        if slice.Bars is None:
            return
        bar = slice.Bars.get(self.fut.Symbol)
        if bar is None:
            return
        t = self.Time
        hm = t.hour * 60 + t.minute          # bar end time, ET
        o, h, l, c, v = (float(bar.Open), float(bar.High), float(bar.Low),
                         float(bar.Close), float(bar.Volume))
        if self.day != t.date():
            if self.pos is not None:
                self._close(c, hm)
            self.day = t.date()
            self._reset()
        if t.weekday() >= 5 or not (9 * 60 + 30 < hm <= 16 * 60):
            return
        if hm == 9 * 60 + 31:
            self.o930 = o
            self.px[9 * 60 + 30] = o
        if self.o930 is None:
            return
        self.pv += (h + l + c) / 3.0 * v
        self.vol += v
        vwap = self.pv / self.vol if self.vol > 0 else c
        blk = (hm - 9 * 60 - 31) // 30
        if 0 <= blk < 13:
            self.hi[blk] = h if self.hi[blk] is None else max(self.hi[blk], h)
            self.lo[blk] = l if self.lo[blk] is None else min(self.lo[blk], l)
        if hm in CHECKS:
            self.px[hm] = c

        # path tracking of an open position
        if self.pos is not None:
            p = self.pos
            p["k"] += 1
            e = p["e"]
            for i, bp in enumerate(LEVELS):
                d = e * bp / 10000.0
                if p["up"][i] < 0 and h - e >= d:
                    p["up"][i] = p["k"]
                if p["dn"][i] < 0 and e - l >= d:
                    p["dn"][i] = p["k"]

        mv = abs(c / self.o930 - 1.0)
        hist = self.noise.setdefault(hm, [])
        sigma = sum(hist) / len(hist) if len(hist) >= 14 else None
        hist.append(mv)
        if len(hist) > 14:
            hist.pop(0)

        if hm == 16 * 60:
            if self.pc is not None and len(self.px) == len(CHECKS) and None not in self.hi:
                pxs = ",".join(f"{self.px[x]:.2f}" for x in CHECKS)
                self._emit(f"P,{t.strftime('%Y%m%d')},{t.weekday()},{self.pc:.2f},{pxs},"
                           + ",".join(f"{x:.2f}" for x in self.hi) + ","
                           + ",".join(f"{x:.2f}" for x in self.lo))
            self.pc = c
            return

        if self.pos is not None and hm >= EOD:
            self._close(c, hm)
            return
        if self.pc is None or sigma is None or hm % 30 != 0 or hm < 10 * 60 or hm >= EOD:
            return
        ub = max(self.o930, self.pc) * (1.0 + sigma)
        lb = min(self.o930, self.pc) * (1.0 - sigma)
        side = 1 if c > ub else (-1 if c < lb else 0)
        if self.pos is not None:
            p = self.pos
            stop_out = (c < max(ub, vwap)) if p["side"] == 1 else (c > min(lb, vwap))
            if stop_out or (side != 0 and side != p["side"]):
                self._close(c, hm)
        if self.pos is None and side != 0:
            self.pos = {"side": side, "e": c, "hm": hm, "k": 0, "sig": sigma,
                        "up": [-1] * len(LEVELS), "dn": [-1] * len(LEVELS)}

    def _close(self, px, hm):
        p = self.pos
        self.pos = None
        self._emit(f"Z,{self.day.strftime('%Y%m%d')},{p['side']},{p['hm']},{p['e']:.2f},{hm},{px:.2f},"
                   f"{p['sig'] * 1e4:.1f}," + ",".join(str(x) for x in p["up"]) + ","
                   + ",".join(str(x) for x in p["dn"]))

    def _emit(self, tag):
        try:
            sym = self.fut.Mapped
            if sym is not None and sym in self.Securities:
                px = self.Securities[sym].Price
                if px > 0:
                    tkt = self.LimitOrder(sym, 1, round(px * 0.5, 0), tag=tag)
                    tkt.Cancel()
                    self.n_tags += 1
        except Exception as ex:
            self.Debug(f"tag fail: {ex}")

    def OnEndOfAlgorithm(self):
        self.Log(f"TAGS={self.n_tags}")
