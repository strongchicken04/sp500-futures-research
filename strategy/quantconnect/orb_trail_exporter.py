# region imports
from AlgorithmImports import *
# endregion
#
# ORB TRAIL EXPORTER: the book's ORB long under different exits, all run side
# by side on the same NQ minute data, one tag per day with each variant's P&L.
#
# Entry (as in the book): after 09:45 ET and before 15:00, a 5-minute close
# above the 09:30-09:45 high and above the session VWAP, while flat; re-entry
# after every exit. Exits, checked on every 1-minute bar (a minute touching
# both the stop and the target counts as the stop):
#   trail  "5m"  stop raised to the 20-EMA of 5-minute closes at each 5m close
#          "1m"  stop raised to the 20-EMA of 1-minute closes at each minute
#          "no"  no trailing
#   sl0    "or"  max(OR low, entry - OR range), the book's initial stop,
#          or a fixed distance in points
#   tp     None, or a fixed target in points
# Flat at 15:55. Wednesday and the volatility gate are applied offline.
#
# Tag: T,<yyyymmdd>,<first variant index>,<pnl pts per variant...>,
#      <trades per variant...>   (variants sent in chunks of CHUNK)

VARIANTS = []
for trail in ("5m", "1m", "no"):
    for sl0 in ("or", 50.0, 100.0, 200.0, 333.0):
        for tp in (None, 75.0, 125.0, 187.5, 250.0):
            if trail == "no" and tp is None:
                continue
            VARIANTS.append((trail, sl0, tp))
EOD = 15 * 60 + 55
CHUNK = 20


class OrbTrailExporter(QCAlgorithm):

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
        self.ema1 = None
        self.ema5 = None
        self._reset()

    def _reset(self):
        self.pv = self.vol = 0.0
        self.orh = self.orl = None
        self.b5 = None
        self.pos = [None] * len(VARIANTS)
        self.pnl = [0.0] * len(VARIANTS)
        self.ntr = [0] * len(VARIANTS)
        self.active = False

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
            self._flush()
            self.day = t.date()
            self._reset()
        if t.weekday() >= 5 or not (9 * 60 + 30 < hm <= 16 * 60):
            return
        self.active = True
        self.pv += (h + l + c) / 3.0 * v
        self.vol += v
        vwap = self.pv / self.vol if self.vol > 0 else c
        if hm <= 9 * 60 + 45:
            self.orh = h if self.orh is None else max(self.orh, h)
            self.orl = l if self.orl is None else min(self.orl, l)

        # exits on this minute, for positions opened before it
        for i, (trail, sl0, tp) in enumerate(VARIANTS):
            p = self.pos[i]
            if p is None:
                continue
            ex = None
            if l <= p["sl"]:
                ex = min(p["sl"], o)        # a stop above the market fills at the open
            elif p["tp"] is not None and h >= p["tp"]:
                ex = max(p["tp"], o)
            elif hm >= EOD:
                ex = c
            if ex is not None:
                self.pnl[i] += ex - p["e"]
                self.ntr[i] += 1
                self.pos[i] = None

        # 1-minute EMA and trail
        k1 = 2.0 / 21
        self.ema1 = c if self.ema1 is None else c * k1 + self.ema1 * (1 - k1)
        for i, (trail, sl0, tp) in enumerate(VARIANTS):
            p = self.pos[i]
            if p is not None and trail == "1m" and self.ema1 > p["sl"]:
                p["sl"] = self.ema1

        b = self.b5
        if b is None:
            self.b5 = b = [h, l, c]
        else:
            b[0], b[1], b[2] = max(b[0], h), min(b[1], l), c
        if hm % 5 != 0:
            return
        self.b5 = None
        k5 = 2.0 / 21
        self.ema5 = b[2] if self.ema5 is None else b[2] * k5 + self.ema5 * (1 - k5)
        for i, (trail, sl0, tp) in enumerate(VARIANTS):
            p = self.pos[i]
            if p is not None and trail == "5m" and self.ema5 > p["sl"]:
                p["sl"] = self.ema5
        if self.orh is None or not (9 * 60 + 45 < hm < 15 * 60):
            return
        cl = b[2]
        if cl > self.orh and cl > vwap:
            rng = self.orh - self.orl
            for i, (trail, sl0, tp) in enumerate(VARIANTS):
                if self.pos[i] is not None:
                    continue
                sl = max(self.orl, cl - rng) if sl0 == "or" else cl - sl0
                if sl >= cl:
                    continue
                self.pos[i] = {"e": cl, "sl": sl, "tp": (cl + tp) if tp is not None else None}

    def _flush(self):
        if not self.active:
            return
        for i in range(len(VARIANTS)):
            if self.pos[i] is not None:          # no 15:55 bar (half day)
                self.ntr[i] += 1
                self.pos[i] = None
        if sum(self.ntr) == 0:
            return
        for j in range(0, len(VARIANTS), CHUNK):
            tag = (f"T,{self.day.strftime('%Y%m%d')},{j},"
                   + ",".join(f"{x:.2f}" for x in self.pnl[j:j + CHUNK]) + ","
                   + ",".join(str(x) for x in self.ntr[j:j + CHUNK]))
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
        self._flush()
        self.Log(f"TAGS={self.n_tags} VARIANTS={len(VARIANTS)}")
