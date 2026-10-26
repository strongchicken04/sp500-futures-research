# region imports
from AlgorithmImports import *
# endregion

# VIX-implied daily band test.
#
# Kazdy den zaznamena:
#   nq_open, nq_high, nq_low, nq_close  (RTH 9:30-16:00 ET, NQ front-month)
#   vix_prev  (VIX close z predchoziho dne)
# Lokalne pak: pasmo = open * (vix_prev / 15.87 / 100), check zda [low, high]
# lezi cele v [open - pasmo, open + pasmo].
#
# Tag: VB,date,nq_open,nq_high,nq_low,nq_close,vix_prev


class NQVixBand(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2018, 1, 1)
        self.SetEndDate(2025, 12, 31)
        self.SetCash(1_000_000)
        f = self.AddFuture(
            Futures.Indices.NASDAQ_100_E_MINI, Resolution.Minute,
            dataNormalizationMode=DataNormalizationMode.Raw,
            dataMappingMode=DataMappingMode.OpenInterest,
            contractDepthOffset=0, extendedMarketHours=True)
        f.SetFilter(0, 120)
        self.future = f
        self.cont = f.Symbol
        self.vix = self.AddIndex("VIX", Resolution.Minute).Symbol

        self.cur_date = None
        self.n_tags = 0

        # denni stavy
        self.day_open = None
        self.day_high = None
        self.day_low = None
        self.day_close = None
        self.vix_prev_close = None       # posledni znama VIX close z predchoziho dne
        self.vix_today_last = None       # bezici VIX z dneska (bude prev pro zitrek)
        self.emitted_today = False

    def _reset_day(self):
        self.day_open = None
        self.day_high = None
        self.day_low = None
        self.day_close = None
        self.emitted_today = False

    def _emit(self, tag):
        try:
            sym = self.future.Mapped
            if sym is not None and sym in self.Securities and self.Securities[sym].Price > 0:
                tkt = self.LimitOrder(sym, 1, round(self.Securities[sym].Price * 0.5, 2), tag=tag)
                tkt.Cancel()
                self.n_tags += 1
        except Exception as e:
            self.Debug(f"tag fail: {e}")

    def OnData(self, slice: Slice):
        t = self.Time
        d = t.date()

        if self.cur_date is None:
            self.cur_date = d

        # Prechod na novy den -> emit predchoziho + posun VIX prev
        if d != self.cur_date:
            if (self.day_open is not None and self.day_high is not None
                    and self.day_low is not None and self.day_close is not None
                    and self.vix_prev_close is not None
                    and not self.emitted_today):
                self._emit(f"VB,{self.cur_date.strftime('%Y-%m-%d')},"
                           f"{self.day_open:.2f},{self.day_high:.2f},"
                           f"{self.day_low:.2f},{self.day_close:.2f},"
                           f"{self.vix_prev_close:.2f}")
                self.emitted_today = True
            # VIX "prev" pro dalsi den = posledni znama hodnota z minuleho dne
            if self.vix_today_last is not None:
                self.vix_prev_close = self.vix_today_last
            self.cur_date = d
            self._reset_day()

        mend = t.hour * 60 + t.minute

        # VIX update (bezici, ETH kryte indexem)
        if slice.Bars is not None and self.vix in slice.Bars:
            self.vix_today_last = slice.Bars[self.vix].Close

        # NQ RTH 9:30 - 16:00 ET  (mend 571-960)
        if not (571 <= mend <= 960):
            return
        bar = slice.Bars.get(self.cont) if slice.Bars is not None else None
        if bar is None:
            return

        if self.day_open is None:
            self.day_open = bar.Open
            self.day_high = bar.High
            self.day_low = bar.Low
        else:
            self.day_high = max(self.day_high, bar.High)
            self.day_low = min(self.day_low, bar.Low)
        self.day_close = bar.Close

    def OnEndOfAlgorithm(self):
        # emit posledni den, pokud je hotovy
        if (self.day_open is not None and self.day_high is not None
                and self.day_low is not None and self.day_close is not None
                and self.vix_prev_close is not None
                and not self.emitted_today):
            self._emit(f"VB,{self.cur_date.strftime('%Y-%m-%d')},"
                       f"{self.day_open:.2f},{self.day_high:.2f},"
                       f"{self.day_low:.2f},{self.day_close:.2f},"
                       f"{self.vix_prev_close:.2f}")
        self.Log(f"VB_TAGS={self.n_tags}")
