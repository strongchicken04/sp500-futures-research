# region imports
from AlgorithmImports import *
from collections import deque
# endregion
#
# VWAP TREND EXPORTER (Zarattini & Aziz 2023, "VWAP: the Holy Grail for day
# trading systems"): always in the market during RTH, long while the bar
# closes above the session VWAP, short while below; flip at the close of the
# bar that crosses; flat at the 15:55 close. Per day and variant one tag with
# the gross result and the number of position changes, so costs are applied
# offline.
#   V1   1-minute bars
#   V5   5-minute bars
#   V15  15-minute bars
#   B5   5-minute bars with a 0.10% buffer (flip only beyond VWAP +/- 0.10%)
# VWAP from 1-minute hlc3 x volume from 09:31.
#
# Tag: W,<variant>,<yyyymmdd>,<gross pts>,<entries>,<rv20 x1000>

TICKER = Futures.Indices.NASDAQ_100_E_MINI
VARIANTS = {"V1": (1, 0.0), "V5": (5, 0.0), "V15": (15, 0.0), "B5": (5, 0.001)}
EOD = 15 * 60 + 55


class VwapTrendExporter(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2018, 1, 1)
        self.SetEndDate(2025, 12, 31)
        self.SetCash(1_000_000)
        self.n_tags = 0
        self.fut = self.AddFuture(TICKER, Resolution.Minute,
                                  dataNormalizationMode=DataNormalizationMode.Raw,
                                  dataMappingMode=DataMappingMode.OpenInterest,
                                  contractDepthOffset=0, extendedMarketHours=False)
        self.fut.SetFilter(0, 180)
        self.closes = deque(maxlen=21)
        self.day = None

    def _rv20(self):
        xs = list(self.closes)
        if len(xs) < 21:
            return 0
        r = [xs[i] / xs[i - 1] - 1.0 for i in range(1, len(xs))]
        m = sum(r) / len(r)
        return int(round((sum((x - m) ** 2 for x in r) / (len(r) - 1)) ** 0.5 * 252 ** 0.5 * 1000))

    def _new_day(self):
        self.rv = self._rv20()
        self.pv = self.v = 0.0
        self.st = {k: {"pos": 0, "e": None, "pnl": 0.0, "n": 0} for k in VARIANTS}
        self.done = False

    def OnData(self, slice):
        if slice.Bars is None:
            return
        bar = slice.Bars.get(self.fut.Symbol)
        if bar is None:
            return
        t = self.Time
        hm = t.hour * 60 + t.minute
        if not (9 * 60 + 30 < hm <= 16 * 60) or t.weekday() >= 5:
            return
        if self.day != t.date():
            self.day = t.date()
            self._new_day()
        h, l, c, v = float(bar.High), float(bar.Low), float(bar.Close), float(bar.Volume)
        if hm == 16 * 60:
            self.closes.append(c)
        if self.done:
            return
        self.pv += (h + l + c) / 3.0 * v
        self.v += v
        vw = self.pv / self.v if self.v > 0 else c
        mins = hm - (9 * 60 + 30)
        for k, (tf, buf) in VARIANTS.items():
            s = self.st[k]
            if hm == EOD:
                if s["pos"] != 0:
                    s["pnl"] += s["pos"] * (c - s["e"])
                continue
            if mins % tf != 0:
                continue
            want = 1 if c > vw * (1 + buf) else (-1 if c < vw * (1 - buf) else s["pos"])
            if want != 0 and want != s["pos"]:
                if s["pos"] != 0:
                    s["pnl"] += s["pos"] * (c - s["e"])
                s["pos"], s["e"] = want, c
                s["n"] += 1
        if hm == EOD:
            self.done = True
            d = self.day.strftime('%Y%m%d')
            for k, s in self.st.items():
                self._emit(f"W,{k},{d},{s['pnl']:.2f},{s['n']},{self.rv}")

    def _emit(self, tag):
        try:
            sym = self.fut.Mapped
            if sym is not None and sym in self.Securities:
                px = self.Securities[sym].Price
                if px > 0:
                    mpv = float(self.Securities[sym].SymbolProperties.MinimumPriceVariation)
                    tkt = self.LimitOrder(sym, 1, round(px * 0.5 / mpv) * mpv, tag=tag)
                    tkt.Cancel()
                    self.n_tags += 1
        except Exception as ex:
            self.Debug(f"tag fail: {ex}")

    def OnEndOfAlgorithm(self):
        self.Log(f"TAGS={self.n_tags}")
