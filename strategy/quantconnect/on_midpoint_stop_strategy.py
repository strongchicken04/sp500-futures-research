# region imports
from AlgorithmImports import *
# endregion

# Strategy: at RTH open (9:30 ET):
#   ONM = (ONH + ONL) / 2  (from 18:00 prev day - 9:30 today Globex range)
#   if RTH open > ONM: LONG,  TP = ONH,   SL = ONM
#   if RTH open < ONM: SHORT, TP = ONL,   SL = ONM
# Asymmetric structure-based bracket. TP dist = |extreme - open|,
# SL dist = |open - ONM|. Ratio varies by where open sits in [ONM, extreme].
# If neither hit -> EOD close.
#
# Tag: OMS,date,dir,open,onh,onl,onm,tp,sl,close,result,pnl,mae,mfe
#   result = T (TP first) / S (SL first) / B (same-minute -> SL) /
#            E (EOD) / X (skipped)


class NQOnMidStopStrategy(QCAlgorithm):

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
        self.dir = 0
        self.tp_lvl = None
        self.sl_lvl = None
        self.result = None
        self.emitted_today = False
        self.mae = 0.0
        self.mfe = 0.0

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

        if in_on:
            if self.on_h is None:
                self.on_h = bar.High
                self.on_l = bar.Low
            else:
                self.on_h = max(self.on_h, bar.High)
                self.on_l = min(self.on_l, bar.Low)

        if self.cur_date is None:
            self.cur_date = d
        elif d != self.cur_date:
            if not self.emitted_today:
                self._emit_day(bar_close=bar.Close)
            self._reset_rth()
            self.cur_date = d

        if mend == 571 and self.rth_open is None and self.on_h is not None:
            self.rth_open = bar.Open
            self.onh_frozen = self.on_h
            self.onl_frozen = self.on_l
            onm = (self.onh_frozen + self.onl_frozen) / 2.0

            if self.rth_open > onm:
                self.dir = 1
                self.tp_lvl = self.onh_frozen
                self.sl_lvl = onm
            elif self.rth_open < onm:
                self.dir = -1
                self.tp_lvl = self.onl_frozen
                self.sl_lvl = onm
            else:
                self.dir = 0
                self.result = "X"

            self.on_h = None
            self.on_l = None

        if in_rth and self.dir != 0 and self.result is None:
            if self.dir == 1:
                self.mfe = max(self.mfe, bar.High - self.rth_open)
                self.mae = max(self.mae, self.rth_open - bar.Low)
                tp_hit = bar.High >= self.tp_lvl
                sl_hit = bar.Low <= self.sl_lvl
            else:
                self.mfe = max(self.mfe, self.rth_open - bar.Low)
                self.mae = max(self.mae, bar.High - self.rth_open)
                tp_hit = bar.Low <= self.tp_lvl
                sl_hit = bar.High >= self.sl_lvl
            if tp_hit and sl_hit:
                self.result = "B"
            elif tp_hit:
                self.result = "T"
            elif sl_hit:
                self.result = "S"

        if mend == 960 and not self.emitted_today and self.rth_open is not None:
            self._emit_day(bar_close=bar.Close)
            self.emitted_today = True

    def _emit_day(self, bar_close):
        if self.rth_open is None or self.onh_frozen is None:
            return
        onm = (self.onh_frozen + self.onl_frozen) / 2.0
        if self.result is None:
            self.result = "E"
        if self.result == "T":
            pnl = self.dir * (self.tp_lvl - self.rth_open)
        elif self.result in ("S", "B"):
            pnl = self.dir * (self.sl_lvl - self.rth_open)
        elif self.result == "E":
            pnl = self.dir * (bar_close - self.rth_open)
        else:
            pnl = 0.0
        tp_s = f"{self.tp_lvl:.2f}" if self.tp_lvl is not None else "-"
        sl_s = f"{self.sl_lvl:.2f}" if self.sl_lvl is not None else "-"
        self._emit(f"OMS,{self.cur_date.strftime('%Y-%m-%d')},{self.dir},"
                   f"{self.rth_open:.2f},{self.onh_frozen:.2f},{self.onl_frozen:.2f},"
                   f"{onm:.2f},{tp_s},{sl_s},{bar_close:.2f},{self.result},{pnl:.2f},"
                   f"{self.mae:.2f},{self.mfe:.2f}")

    def OnEndOfAlgorithm(self):
        self.Log(f"OMS_TAGS={self.n_tags}")
