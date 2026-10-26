# region imports
from AlgorithmImports import *
# endregion

# Overnight level reaction test.
#
# For each RTH day (9:30-16:00 ET), given ON range (18:00 prev - 9:30):
#   ONH = overnight high, ONL = overnight low
# Track FIRST touch of ONH and ONL during RTH (1-min bar granularity),
# then measure post-touch extremes:
#   For ONH first touch (bar where high >= ONH):
#     cont_H = max(high) after touch - ONH   (continuation up, positive pts)
#     fade_H = ONH - min(low) after touch    (fade/reversal down, positive pts)
#   For ONL first touch (bar where low <= ONL):
#     cont_L = ONL - min(low) after touch    (continuation down, positive pts)
#     fade_L = max(high) after touch - ONL   (fade/reversal up, positive pts)
#
# Also emit RTH close for context.
#
# Tag: OR,date,rth_open,onh,onl,touch_H,cont_H,fade_H,touch_L,cont_L,fade_L,close
#   touch_H / touch_L = 1 if touched during RTH else 0


class NQOnLevelReactions(QCAlgorithm):

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
        self.n_tags = 0

        self.on_h = None
        self.on_l = None
        self.cur_date = None
        self._reset_rth()

    def _reset_rth(self):
        self.rth_open = None
        self.onh_frozen = None
        self.onl_frozen = None
        self.touch_H = False
        self.touch_L = False
        self.cont_H = 0.0
        self.fade_H = 0.0
        self.cont_L = 0.0
        self.fade_L = 0.0
        self.rth_close = None
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
        bar = slice.Bars.get(self.cont) if slice.Bars is not None else None
        if bar is None:
            return

        t = self.Time
        d = t.date()
        mend = t.hour * 60 + t.minute
        in_on = (mend >= 1080) or (mend <= 570)
        in_rth = 571 <= mend <= 960

        # accumulate ON range (reset happens at 9:30 open freeze below)
        if in_on:
            if self.on_h is None:
                self.on_h = bar.High
                self.on_l = bar.Low
            else:
                self.on_h = max(self.on_h, bar.High)
                self.on_l = min(self.on_l, bar.Low)

        # date rollover
        if self.cur_date is None:
            self.cur_date = d
        elif d != self.cur_date:
            if not self.emitted_today:
                self._emit_day(bar_close=(self.rth_close if self.rth_close else bar.Close))
            self._reset_rth()
            self.cur_date = d

        # RTH open snapshot at 9:30
        if mend == 571 and self.rth_open is None and self.on_h is not None:
            self.rth_open = bar.Open
            self.onh_frozen = self.on_h
            self.onl_frozen = self.on_l
            self.on_h = None
            self.on_l = None

        if not in_rth or self.rth_open is None:
            return

        self.rth_close = bar.Close

        # ---- ONH touch detection + post-touch extremes ----
        if not self.touch_H:
            if bar.High >= self.onh_frozen:
                self.touch_H = True
                # measure from this bar's H/L too (post-touch includes the touch bar)
                self.cont_H = max(0.0, bar.High - self.onh_frozen)
                self.fade_H = max(0.0, self.onh_frozen - bar.Low)
        else:
            self.cont_H = max(self.cont_H, bar.High - self.onh_frozen)
            self.fade_H = max(self.fade_H, self.onh_frozen - bar.Low)

        # ---- ONL touch detection + post-touch extremes ----
        if not self.touch_L:
            if bar.Low <= self.onl_frozen:
                self.touch_L = True
                self.cont_L = max(0.0, self.onl_frozen - bar.Low)
                self.fade_L = max(0.0, bar.High - self.onl_frozen)
        else:
            self.cont_L = max(self.cont_L, self.onl_frozen - bar.Low)
            self.fade_L = max(self.fade_L, bar.High - self.onl_frozen)

        # RTH close: emit
        if mend == 960 and not self.emitted_today:
            self._emit_day(bar_close=bar.Close)
            self.emitted_today = True

    def _emit_day(self, bar_close):
        if self.rth_open is None or self.onh_frozen is None:
            return
        self._emit(f"OR,{self.cur_date.strftime('%Y-%m-%d')},"
                   f"{self.rth_open:.2f},{self.onh_frozen:.2f},{self.onl_frozen:.2f},"
                   f"{1 if self.touch_H else 0},{self.cont_H:.2f},{self.fade_H:.2f},"
                   f"{1 if self.touch_L else 0},{self.cont_L:.2f},{self.fade_L:.2f},"
                   f"{bar_close:.2f}")

    def OnEndOfAlgorithm(self):
        self.Log(f"OR_TAGS={self.n_tags}")
