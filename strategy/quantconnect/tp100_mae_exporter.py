# region imports
from AlgorithmImports import *
from collections import deque
# endregion

# MAE exporter for the TP-100pt version of the VWAP band strategy on real NQ.
#
# For each day's FIRST band trade (entry: 1-min close beyond session-VWAP +/-20bps
# from 9:31): the TP100 version exits at entry +/- 100 pts (limit, intrabar) or,
# if never reached, at the original exit (close beyond opposite band / 16:00 ET).
# Records the MAX ADVERSE EXCURSION (points against the position):
#   mae_pre  = through the bar BEFORE the TP-touch bar (clean pre-touch heat)
#   mae_incl = including the touch bar's adverse extreme (conservative)
# For non-TP trades both equal the full-trade MAE.
# Tag: date,dir,entry,tp_hit,mae_pre,mae_incl,pnl_pts,gap_ok,trend_ok

BAND = 0.002
TP_PTS = 100.0
GAP_PCT = 25.0
TREND_PCT = 60.0


class NQTp100MAE(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2018, 1, 1)
        self.SetEndDate(2025, 12, 31)
        self.SetCash(1_000_000)
        f = self.AddFuture(
            Futures.Indices.NASDAQ100EMini, Resolution.Minute,
            dataNormalizationMode=DataNormalizationMode.Raw,
            dataMappingMode=DataMappingMode.OpenInterest,
            contractDepthOffset=0, extendedMarketHours=True)
        f.SetFilter(0, 120)
        self.future = f
        self.cont = f.Symbol
        self.cur_date = None
        self.prev_day = None
        self.gap_hist = deque(maxlen=250)
        self.trend_hist = deque(maxlen=250)
        self.n_tags = 0
        self._reset_day()

    def _reset_day(self):
        self.cpv = 0.0
        self.cv = 0.0
        self.pos = 0
        self.entry = 0.0
        self.adverse = 0.0          # running max adverse (points, >=0)
        self.traded = False
        self.gap_ok = True
        self.trend_ok = True
        self.d_open = None
        self.d_high = None
        self.d_low = None
        self.d_close = None

    @staticmethod
    def _rank(hist, v):
        if len(hist) < 60 or v is None:
            return None
        n = 0
        for x in hist:
            if x <= v:
                n += 1
        return 100.0 * n / len(hist)

    def _compute_gates(self, today_open):
        if self.prev_day is not None:
            po, ph, pl, pc = self.prev_day
            ytr = abs(pc - po) / (ph - pl) if ph > pl else None
            r = self._rank(self.trend_hist, ytr)
            self.trend_ok = True if r is None else (r <= TREND_PCT)
            if ytr is not None:
                self.trend_hist.append(ytr)
            gap = abs(today_open / pc - 1.0) if pc > 0 else None
            r = self._rank(self.gap_hist, gap)
            self.gap_ok = True if r is None else (r >= GAP_PCT)
            if gap is not None:
                self.gap_hist.append(gap)

    def _emit(self, date, direction, tp_hit, mae_pre, mae_incl, pnl):
        tag = (f"{date.strftime('%Y-%m-%d')},{direction},{self.entry:.2f},{int(tp_hit)},"
               f"{mae_pre:.2f},{mae_incl:.2f},{pnl:.2f},{int(self.gap_ok)},{int(self.trend_ok)}")
        try:
            sym = self.future.Mapped
            if sym is not None and sym in self.Securities and self.Securities[sym].Price > 0:
                tkt = self.LimitOrder(sym, 1, round(self.Securities[sym].Price * 0.5, 2), tag=tag)
                tkt.Cancel()
                self.n_tags += 1
        except Exception as e:
            self.Debug(f"tag fail {date}: {e}")

    def OnData(self, slice: Slice):
        bar = slice.Bars.get(self.cont) if slice.Bars is not None else None
        if bar is None:
            return
        t = self.Time
        d = t.date()
        if self.cur_date is None:
            self.cur_date = d
        if d != self.cur_date:
            if self.d_open is not None:
                self.prev_day = (self.d_open, self.d_high, self.d_low, self.d_close)
            self.cur_date = d
            self._reset_day()

        mend = t.hour * 60 + t.minute
        if not (571 <= mend <= 960):
            return
        if self.d_open is None:
            self.d_open, self.d_high, self.d_low = bar.Open, bar.High, bar.Low
            self._compute_gates(bar.Open)
        self.d_high = max(self.d_high, bar.High)
        self.d_low = min(self.d_low, bar.Low)
        self.d_close = bar.Close

        hlc3 = (bar.High + bar.Low + bar.Close) / 3.0
        self.cpv += hlc3 * float(bar.Volume)
        self.cv += float(bar.Volume)
        if self.cv <= 0:
            return
        vwap = self.cpv / self.cv
        up, dn = vwap * (1 + BAND), vwap * (1 - BAND)

        if self.pos != 0:
            mae_pre = self.adverse            # through previous bar
            bar_adv = (self.entry - bar.Low) if self.pos == 1 else (bar.High - self.entry)
            mae_incl = max(self.adverse, bar_adv, 0.0)
            fav = (bar.High - self.entry) if self.pos == 1 else (self.entry - bar.Low)
            if fav >= TP_PTS:                 # TP100 touched -> trade ends here
                self._emit(d, self.pos, True, mae_pre, mae_incl, TP_PTS)
                self.pos = 0
            else:
                self.adverse = mae_incl
                if mend == 960:
                    pnl = self.pos * (bar.Close - self.entry)
                    self._emit(d, self.pos, False, self.adverse, self.adverse, pnl)
                    self.pos = 0
                elif self.pos == 1 and bar.Close < dn:
                    pnl = bar.Close - self.entry
                    self._emit(d, 1, False, self.adverse, self.adverse, pnl)
                    self.pos = 0
                elif self.pos == -1 and bar.Close > up:
                    pnl = self.entry - bar.Close
                    self._emit(d, -1, False, self.adverse, self.adverse, pnl)
                    self.pos = 0

        if mend == 960 or mend < 572:
            return
        if self.pos == 0 and not self.traded:
            if bar.Close > up:
                self.pos, self.entry, self.traded = 1, bar.Close, True
                self.adverse = 0.0
            elif bar.Close < dn:
                self.pos, self.entry, self.traded = -1, bar.Close, True
                self.adverse = 0.0

    def OnEndOfAlgorithm(self):
        self.Log(f"TP100_MAE_TAGS={self.n_tags}")
