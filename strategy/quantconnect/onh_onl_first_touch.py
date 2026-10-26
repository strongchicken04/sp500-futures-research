# region imports
from AlgorithmImports import *
# endregion

# Overnight range "first touch" test.
#
# Definice:
#   ON session = 18:00 ET (prev day) az 9:30 ET (current day)
#                = Globex reopen po CME maintenance breaku
#   ONH, ONL   = high/low tehle ON session
#   ONM        = (ONH + ONL) / 2
#   RTH        = 9:30 - 16:00 ET
#
# Kazdy den zaznamena:
#   date, rth_open, onh, onl, onm, first_touch, open_side
# kde:
#   first_touch = "H"  ONH hit first during RTH
#                 "L"  ONL hit first
#                 "B"  both in the same 1-min bar (ambivalent)
#                 "N"  neither hit during RTH
#   open_side   = "A"  rth_open > ONM
#                 "B"  rth_open < ONM
#                 "M"  rth_open == ONM
#
# Tag: ON,date,open,onh,onl,onm,first,side


class NQOnFirstTouch(QCAlgorithm):

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

        # ON tracking (updates during ETH, frozen at 9:30)
        self.on_h = None
        self.on_l = None
        # per RTH day
        self.rth_open = None
        self.onh_frozen = None
        self.onl_frozen = None
        self.first_touch = None
        self.cur_date = None
        self.emitted_today = False

    def _reset_rth(self):
        self.rth_open = None
        self.onh_frozen = None
        self.onl_frozen = None
        self.first_touch = None
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
        mend = t.hour * 60 + t.minute       # minute-of-day (bar close time)

        # ON session = 18:00 (1080) - 9:30 (570)  crosses midnight
        # We treat "current ON session" as: bars with mend >= 1080 OR mend <= 570
        in_on = (mend >= 1080) or (mend <= 570)
        # RTH bars: 9:30 close bar = 571, ... 16:00 close = 960
        in_rth = 571 <= mend <= 960

        # ON tracking: accumulate whenever inside ON window.
        # Reset happens at 9:30 open freeze (below).
        if in_on:
            if self.on_h is None:
                self.on_h = bar.High
                self.on_l = bar.Low
            else:
                self.on_h = max(self.on_h, bar.High)
                self.on_l = min(self.on_l, bar.Low)

        # Date change -> safety emit if RTH-hotova a nevyemitovana, pak reset a advance
        if self.cur_date is None:
            self.cur_date = d
        elif d != self.cur_date:
            if not self.emitted_today:
                self._emit_prev_day()
            self._reset_rth()
            self.cur_date = d

        # RTH open snapshot at 9:30 bar (mend == 571 = first RTH bar close).
        # Freeze ON high/low for today, then reset for tonight's accumulation.
        if mend == 571 and self.rth_open is None:
            self.rth_open = bar.Open
            self.onh_frozen = self.on_h
            self.onl_frozen = self.on_l
            self.on_h = None
            self.on_l = None

        # First-touch detection during RTH
        if in_rth and self.rth_open is not None and self.onh_frozen is not None \
                and self.first_touch is None:
            hit_h = bar.High >= self.onh_frozen
            hit_l = bar.Low <= self.onl_frozen
            if hit_h and hit_l:
                self.first_touch = "B"       # ambivalent (same 1-min bar)
            elif hit_h:
                self.first_touch = "H"
            elif hit_l:
                self.first_touch = "L"

        # At RTH close (mend == 960) -> emit
        if mend == 960 and not self.emitted_today and self.rth_open is not None:
            self._emit_prev_day(now_date=d)
            self.emitted_today = True

    def _emit_prev_day(self, now_date=None):
        d = now_date if now_date is not None else self.cur_date
        if (self.rth_open is None or self.onh_frozen is None
                or self.onl_frozen is None):
            return
        onm = (self.onh_frozen + self.onl_frozen) / 2.0
        first = self.first_touch if self.first_touch else "N"
        if self.rth_open > onm:
            side = "A"
        elif self.rth_open < onm:
            side = "B"
        else:
            side = "M"
        self._emit(f"ON,{d.strftime('%Y-%m-%d')},{self.rth_open:.2f},"
                   f"{self.onh_frozen:.2f},{self.onl_frozen:.2f},{onm:.2f},"
                   f"{first},{side}")

    def OnEndOfAlgorithm(self):
        self.Log(f"ON_TAGS={self.n_tags}")
