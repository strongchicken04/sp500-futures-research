# region imports
from AlgorithmImports import *
# endregion
#
# ZN DAILY SNAPSHOT EXPORTER: 10-year Treasury note futures prices at fixed
# times every trading day, for calendar effects (month-end, Treasury
# auctions at 13:00 ET) scored offline with any event calendar.
#
# Tag: Z,<yyyymmdd>,<open 08:20>,<close of the bars ending 09:00, 11:30,
#      12:55, 13:05, 13:30, 15:00 ET>,<low 13:00-15:00>,<high 13:00-15:00>

TIMES = [9 * 60, 11 * 60 + 30, 12 * 60 + 55, 13 * 60 + 5, 13 * 60 + 30, 15 * 60]


class ZNDailyExporter(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2018, 1, 1)
        self.SetEndDate(2025, 12, 31)
        self.SetCash(1_000_000)
        self.n_tags = 0
        self.zn = self.AddFuture(Futures.Financials.Y_10_TREASURY_NOTE, Resolution.Minute,
                                 dataNormalizationMode=DataNormalizationMode.Raw,
                                 dataMappingMode=DataMappingMode.OpenInterest,
                                 contractDepthOffset=0, extendedMarketHours=True)
        self.zn.SetFilter(0, 180)
        self.day = None
        self._reset()

    def _reset(self):
        self.o = None
        self.px = {}
        self.lo = self.hi = None

    def OnData(self, slice):
        if slice.Bars is None:
            return
        bar = slice.Bars.get(self.zn.Symbol)
        if bar is None:
            return
        t = self.Time
        hm = t.hour * 60 + t.minute
        if self.day != t.date():
            self.day = t.date()
            self._reset()
        if t.weekday() >= 5:
            return
        if hm == 8 * 60 + 21:
            self.o = float(bar.Open)
        if hm in TIMES:
            self.px[hm] = float(bar.Close)
        if 13 * 60 < hm <= 15 * 60:
            self.lo = float(bar.Low) if self.lo is None else min(self.lo, float(bar.Low))
            self.hi = float(bar.High) if self.hi is None else max(self.hi, float(bar.High))
        if hm == 15 * 60 and self.o is not None and len(self.px) == len(TIMES):
            vals = [self.o] + [self.px[x] for x in TIMES] + [self.lo, self.hi]
            self._emit(f"Z,{t.strftime('%Y%m%d')}," + ",".join(f"{v:.5f}" for v in vals))

    def _emit(self, tag):
        try:
            sym = self.zn.Mapped
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
