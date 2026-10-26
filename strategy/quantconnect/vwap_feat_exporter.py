# region imports
from AlgorithmImports import *
from collections import deque
# endregion
#
# VWAP BAND FEATURE EXPORTER: band breaks with everything needed to size the
# target from the breakout candle and the volatility around it.
#
# For each band distance D in DISTS (bp from the session VWAP), the first
# 5-minute close above VWAP + D (U<D>) and the first below VWAP - D (D<D>)
# after 09:40 and before 15:00 are entries, at that bar's close. Recorded at
# entry, all known by then:
#   c5r   range of the breakout 5-minute candle (points)
#   c5b   its body, signed in the break direction (points)
#   cloc  where it closed in its range, 0 = at the low, 1 = at the high
#   rvol5 its volume / mean volume of the previous 20 RTH 5-minute bars
#   atr5  mean range of the previous 12 RTH 5-minute bars (points)
#   atrd  14-day ATR of the regular session (points)
#   rv20  20-day realised volatility of daily closes, annualised
#   dist  close - VWAP (points)
#   vslp  VWAP now - VWAP 30 minutes earlier (points)
# Then, from the next minute to 15:55, the first minute each LEVELS move (in
# points) up and down is reached.
#
# Tag: V,<yyyymmdd>,<type>,<hhmm>,<entry>,<c5r>,<c5b>,<cloc>,<rvol5>,<atr5>,
#      <atrd>,<rv20>,<dist>,<vslp>,<up x29>,<dn x29>,<eod pts>

DISTS = [10, 20]
LEVELS = [1, 1.5, 2, 2.5, 3, 3.5, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15,
          16.5, 20, 23, 26, 30, 33, 36.5, 40, 43, 46.5, 50]
EOD = 15 * 60 + 55


class VwapFeatExporter(QCAlgorithm):

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
        self.trk = []
        self.trs = deque(maxlen=14)          # daily RTH true ranges
        self.rets = deque(maxlen=21)         # daily RTH closes
        self.r5 = deque(maxlen=12)           # recent 5-minute ranges
        self.v5 = deque(maxlen=20)           # recent 5-minute volumes
        self.pc = None
        self._reset()

    def _reset(self):
        self.pv = self.vol = 0.0
        self.vw_hist = {}
        self.b5 = None
        self.rth_h = self.rth_l = None
        self.started = False
        self.done = set()

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
            for tr in self.trk:
                self._emit(tr)
            self.trk = []
            self.day = t.date()
            self._reset()
        self._track(h, l, c, hm)
        if t.weekday() >= 5 or not (9 * 60 + 30 < hm <= 16 * 60):
            return
        self.started = True
        self.rth_h = h if self.rth_h is None else max(self.rth_h, h)
        self.rth_l = l if self.rth_l is None else min(self.rth_l, l)
        self.pv += (h + l + c) / 3.0 * v
        self.vol += v
        vwap = self.pv / self.vol if self.vol > 0 else c
        self.vw_hist[hm] = vwap

        b = self.b5
        if b is None:
            self.b5 = b = [o, h, l, c, v]
        else:
            b[1], b[2], b[3], b[4] = max(b[1], h), min(b[2], l), c, b[4] + v
        if hm % 5 == 0:
            self.b5 = None
            if (9 * 60 + 40 <= hm < 15 * 60 and self.pc is not None and len(self.trs) == 14
                    and len(self.rets) == 21 and len(self.r5) == 12 and len(self.v5) == 20):
                for d in DISTS:
                    if b[3] > vwap * (1.0 + d / 1e4):
                        self._open(f"U{d}", 1, hm, b, vwap)
                    if b[3] < vwap * (1.0 - d / 1e4):
                        self._open(f"D{d}", -1, hm, b, vwap)
            self.r5.append(b[1] - b[2])
            self.v5.append(b[4])

        if hm == 16 * 60:
            if self.pc is not None:
                self.trs.append(max(self.rth_h - self.rth_l, abs(self.rth_h - self.pc), abs(self.rth_l - self.pc)))
            self.rets.append(c)
            self.pc = c

    def _open(self, typ, side, hm, b, vwap):
        if typ in self.done:
            return
        self.done.add(typ)
        o, h, l, c, v = b
        rng = h - l
        closes = list(self.rets)
        r = [closes[i] / closes[i - 1] - 1.0 for i in range(1, len(closes))]
        mu = sum(r) / len(r)
        rv20 = (sum((x - mu) ** 2 for x in r) / (len(r) - 1)) ** 0.5 * (252 ** 0.5)
        prev = self.vw_hist.get(hm - 30, vwap)
        feat = (rng, side * (c - o), (c - l) / rng if rng > 0 else 0.5,
                v / (sum(self.v5) / len(self.v5)) if sum(self.v5) > 0 else 1.0,
                sum(self.r5) / len(self.r5), sum(self.trs) / len(self.trs), rv20,
                c - vwap, vwap - prev)
        self.trk.append({
            "ctx": f"V,{self.Time.strftime('%Y%m%d')},{typ},{hm},{c:.2f}," + ",".join(f"{x:.4f}" for x in feat),
            "e": c, "k": 0, "up": [-1] * len(LEVELS), "dn": [-1] * len(LEVELS), "last": 0.0})

    def _track(self, h, l, c, hm):
        keep = []
        for tr in self.trk:
            tr["k"] += 1
            e = tr["e"]
            for i, d in enumerate(LEVELS):
                if tr["up"][i] < 0 and h - e >= d:
                    tr["up"][i] = tr["k"]
                if tr["dn"][i] < 0 and e - l >= d:
                    tr["dn"][i] = tr["k"]
            tr["last"] = c - e
            if EOD <= hm <= 16 * 60:
                self._emit(tr)
            else:
                keep.append(tr)
        self.trk = keep

    def _emit(self, tr):
        tag = (tr["ctx"] + "," + ",".join(str(x) for x in tr["up"]) + ","
               + ",".join(str(x) for x in tr["dn"]) + f",{tr['last']:.2f}")
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
