# region imports
from AlgorithmImports import *
# endregion
#
# DAILY BRACKET EXPORTER: what does one big bracketed bet per day look like?
#
# Built to test a pass-the-evaluation-fast idea: a single trade a day with a
# small target and a wide stop (high win rate, negative reward:risk), sized
# so one win is about $1,000. Entry is the close of the 09:31 or the 10:00
# minute; from the next minute on, the first minute each move of LEVELS
# basis points up and down is reached is recorded, to 15:55.
#
# Tag: B,<yyyymmdd>,<entry hhmm>,<entry px>,<up x13>,<dn x13>,<eod pts>
#   up/dn = first minute (1 = the minute after entry) price is LEVELS[i] bp
#   above / below entry, -1 if never by 15:55

LEVELS = [10, 15, 20, 25, 30, 40, 50, 60, 75, 100, 125, 150, 200]
ENTRIES = [9 * 60 + 31, 10 * 60]
EOD = 15 * 60 + 55


class DailyBracketExporter(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2018, 1, 1)
        self.SetEndDate(2025, 12, 31)
        self.SetCash(1_000_000)
        self.n_tags = 0
        self.fut = self.AddFuture(
            Futures.Indices.NASDAQ100EMini, Resolution.Minute,
            dataNormalizationMode=DataNormalizationMode.Raw,
            dataMappingMode=DataMappingMode.OpenInterest,
            contractDepthOffset=0, extendedMarketHours=True)
        self.fut.SetFilter(0, 180)
        self.day = None
        self.trk = []

    def OnData(self, slice):
        if slice.Bars is None:
            return
        bar = slice.Bars.get(self.fut.Symbol)
        if bar is None:
            return
        t = self.Time
        hm = t.hour * 60 + t.minute          # bar end time, ET
        h, l, c = float(bar.High), float(bar.Low), float(bar.Close)
        if self.day != t.date():
            for tr in self.trk:
                self._emit(tr, tr["last"])
            self.trk = []
            self.day = t.date()
        keep = []
        for tr in self.trk:
            tr["k"] += 1
            e = tr["e"]
            for i, bp in enumerate(LEVELS):
                d = e * bp / 10000.0
                if tr["up"][i] < 0 and h - e >= d:
                    tr["up"][i] = tr["k"]
                if tr["dn"][i] < 0 and e - l >= d:
                    tr["dn"][i] = tr["k"]
            tr["last"] = c - e
            if hm >= EOD:
                self._emit(tr, tr["last"])
            else:
                keep.append(tr)
        self.trk = keep
        if hm in ENTRIES and t.weekday() < 5:
            self.trk.append({"ymd": t.strftime("%Y%m%d"), "hm": hm, "e": c, "k": 0,
                             "up": [-1] * len(LEVELS), "dn": [-1] * len(LEVELS),
                             "last": 0.0})

    def _emit(self, tr, eod):
        tag = (f"B,{tr['ymd']},{tr['hm']},{tr['e']:.2f},"
               + ",".join(str(x) for x in tr["up"]) + ","
               + ",".join(str(x) for x in tr["dn"]) + f",{eod:.2f}")
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
