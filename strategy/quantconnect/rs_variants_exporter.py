# region imports
from AlgorithmImports import *
from collections import deque
# endregion
#
# RS VARIANTS EXPORTER: NQ every 5 minutes 10:00-15:00 ET (61 checks a day)
# with relative strength against ES, YM and RTY, VWAP and EMA distance, and
# the sprint-bracket outcome both ways, so RS sprint variants (other indices,
# 5-minute checks, volatility-scaled thresholds, EMA instead of VWAP) can be
# scored offline with exact first-signal timing.
#
# At each check (bar end, everything known then; entry = that bar's close,
# tracking from the NEXT bar):
#   ret              NQ return since the 09:30 open, bp
#   es, ym, rty      NQ return since open minus that index's, bp
#   vw               (price - session VWAP) / price, bp
#   e21              (price - EMA21 of 5-minute closes) / price, bp
#   L, S             outcome in bp of a long / short with target +0.20% and
#                    stop -0.40% (stop fills at the worse of stop and bar open;
#                    a bar touching both = stop), else the 15:55 close
# Per day: rv20 = annualised 20-day realised vol of NQ daily closes (x1000).
#
# Tags (10 checks per tag, 7 tags a day):
#   R,<yyyymmdd>,<part>,<price at 10:00>,<rv20>,<hhmm:ret:es:ym:rty:vw:e21:L:S>;...

START, END = 2018, 2021
CHECKS = list(range(10 * 60, 15 * 60 + 1, 5))
TGT, STP = 0.0020, 0.0040
EOD = 15 * 60 + 55
PER_TAG = 10


class RSVariantsExporter(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(START, 1, 1)
        self.SetEndDate(END, 12, 31)
        self.SetCash(1_000_000)
        self.n_tags = 0
        self.nq = self._fut(Futures.Indices.NASDAQ100EMini)
        self.oth = {"es": self._fut(Futures.Indices.SP500EMini),
                    "ym": self._fut(Futures.Indices.Dow30EMini),
                    "rty": self._fut(Futures.Indices.Russell2000EMini)}
        self.closes = deque(maxlen=21)
        self.ema = None
        self.day = None
        self._reset()

    def _fut(self, ticker):
        f = self.AddFuture(ticker, Resolution.Minute,
                           dataNormalizationMode=DataNormalizationMode.Raw,
                           dataMappingMode=DataMappingMode.OpenInterest,
                           contractDepthOffset=0, extendedMarketHours=True)
        f.SetFilter(0, 180)
        return f

    def _reset(self):
        self.o_nq = None
        self.o_oth = {k: None for k in self.oth}
        self.last_oth = {k: None for k in self.oth}
        self.pv = self.vol = 0.0
        self.rows = []
        self.px10 = None
        self.rv = None
        self.last_c = None

    def _rv20(self):
        xs = list(self.closes)
        if len(xs) < 21:
            return 0
        r = [xs[i] / xs[i - 1] - 1.0 for i in range(1, len(xs))]
        m = sum(r) / len(r)
        var = sum((x - m) ** 2 for x in r) / (len(r) - 1)
        return int(round((var ** 0.5) * (252 ** 0.5) * 1000))

    def OnData(self, slice):
        if slice.Bars is None:
            return
        t = self.Time
        hm = t.hour * 60 + t.minute
        for k, f in self.oth.items():
            b = slice.Bars.get(f.Symbol)
            if b is not None:
                self.last_oth[k] = float(b.Close)
                if hm == 9 * 60 + 31:
                    self.o_oth[k] = float(b.Open)
        bar = slice.Bars.get(self.nq.Symbol)
        if bar is None:
            return
        o, h, l, c, v = (float(bar.Open), float(bar.High), float(bar.Low),
                         float(bar.Close), float(bar.Volume))
        if self.day != t.date():
            self._flush()
            self.day = t.date()
            self._reset()
            self.rv = self._rv20()
        if t.weekday() >= 5 or not (9 * 60 + 30 < hm <= 16 * 60):
            return
        self._track(o, h, l, c, hm)
        if hm == 9 * 60 + 31:
            self.o_nq = o
        if self.o_nq is None:
            return
        self.pv += (h + l + c) / 3.0 * v
        self.vol += v
        vwap = self.pv / self.vol if self.vol > 0 else c
        if hm % 5 == 0:
            k = 2.0 / 22.0
            self.ema = c if self.ema is None else c * k + self.ema * (1 - k)
        if hm == 16 * 60:
            self.closes.append(c)

        if hm in CHECKS and self.ema is not None:
            if hm == CHECKS[0]:
                self.px10 = c
            ret = c / self.o_nq - 1.0
            rel = []
            for kk in ("es", "ym", "rty"):
                oo, ll = self.o_oth[kk], self.last_oth[kk]
                rel.append(int(round((ret - (ll / oo - 1.0)) * 1e4)) if oo and ll else 999)
            self.rows.append({"hm": hm, "e": c,
                              "f": [int(round(ret * 1e4))] + rel +
                                   [int(round((c - vwap) / c * 1e4)), int(round((c - self.ema) / c * 1e4))],
                              "L": None, "S": None})

    def _track(self, o, h, l, c, hm):
        for r in self.rows:
            e = r["e"]
            if r["L"] is None:
                sl, tp = e * (1 - STP), e * (1 + TGT)
                if l <= sl:
                    r["L"] = (min(sl, o) - e) / e * 1e4
                elif h >= tp:
                    r["L"] = TGT * 1e4
            if r["S"] is None:
                sl, tp = e * (1 + STP), e * (1 - TGT)
                if h >= sl:
                    r["S"] = (e - max(sl, o)) / e * 1e4
                elif l <= tp:
                    r["S"] = TGT * 1e4
            if hm == EOD:
                if r["L"] is None:
                    r["L"] = (c - e) / e * 1e4
                if r["S"] is None:
                    r["S"] = (e - c) / e * 1e4
        if hm == EOD:
            self._flush()

    def _flush(self):
        rows = [r for r in self.rows if r["L"] is not None and r["S"] is not None]
        self.rows = []
        if not rows or self.px10 is None:
            return
        d = self.day.strftime('%Y%m%d')
        for p in range(0, len(rows), PER_TAG):
            body = ";".join(f"{r['hm']}:" + ":".join(str(x) for x in r["f"]) + f":{r['L']:.0f}:{r['S']:.0f}"
                            for r in rows[p:p + PER_TAG])
            self._emit(f"R,{d},{p // PER_TAG},{self.px10:.2f},{self.rv},{body}")

    def _emit(self, tag):
        try:
            sym = self.nq.Mapped
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
