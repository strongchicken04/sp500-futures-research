# region imports
from AlgorithmImports import *
from collections import deque
# endregion

# MFE exporter for the VWAP hysteresis-band strategy on REAL NQ minute data.
#
# For every day's FIRST band trade (entry from the 9:31 candle close beyond
# session-VWAP +/- 20 bps; exit when a 1-min close crosses the OPPOSITE band, or
# at 16:00 ET) it records the maximum favorable excursion (MFE) and maximum
# adverse excursion (MAE) in NQ INDEX POINTS between entry and exit.
#
# Free tier blocks ObjectStore writes and log export, so each day's record is
# exfiltrated through an order tag (far-from-market limit order, cancelled
# immediately, never fills) and read back via the backtests/orders/read API.
# Tag: date,dir,entry,exit,mfe_pts,mae_pts,reason,gap_ok,trend_ok
#
# Gates (gap 25th pct / trend 60th pct, 250-day past-only rolling percentile)
# are recorded as FLAGS only - the trade is taken every day so both "all days"
# and "final config days" averages can be computed offline.

BAND = 0.002          # 20 bps
GAP_PCT = 25.0
TREND_PCT = 60.0


class NQVwapBandMFE(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2008, 1, 1)          # QC NQ minute data starts when it starts
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

        self.cur_date = None
        self.prev_day = None                    # yesterday's RTH (o, h, l, c)
        self.gap_hist = deque(maxlen=250)
        self.trend_hist = deque(maxlen=250)
        self.n_tags = 0
        self._reset_day()

    def _reset_day(self):
        self.cpv = 0.0
        self.cv = 0.0
        self.pos = 0
        self.entry = 0.0
        self.hi = None
        self.lo = None
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
            # trend gate: yesterday's trendiness vs its past distribution
            ytr = abs(pc - po) / (ph - pl) if ph > pl else None
            r = self._rank(self.trend_hist, ytr)
            self.trend_ok = True if r is None else (r <= TREND_PCT)
            if ytr is not None:
                self.trend_hist.append(ytr)
            # gap gate: |overnight gap| vs its past distribution
            gap = abs(today_open / pc - 1.0) if pc > 0 else None
            r = self._rank(self.gap_hist, gap)
            self.gap_ok = True if r is None else (r >= GAP_PCT)
            if gap is not None:
                self.gap_hist.append(gap)

    def _emit(self, date, direction, entry, exitpx, reason):
        mfe = (self.hi - entry) if direction == 1 else (entry - self.lo)
        mae = (entry - self.lo) if direction == 1 else (self.hi - entry)
        tag = (f"{date.strftime('%Y-%m-%d')},{direction},{entry:.2f},{exitpx:.2f},"
               f"{mfe:.2f},{mae:.2f},{reason},{int(self.gap_ok)},{int(self.trend_ok)}")
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
        t = self.Time                              # bar END time
        d = t.date()
        if self.cur_date is None:
            self.cur_date = d
        if d != self.cur_date:                     # new day -> finalize yesterday
            if self.d_open is not None:
                self.prev_day = (self.d_open, self.d_high, self.d_low, self.d_close)
            self.cur_date = d
            self._reset_day()

        mend = t.hour * 60 + t.minute
        if not (571 <= mend <= 960):               # RTH bars only (ends 9:31..16:00)
            return

        if self.d_open is None:                    # first RTH bar of the day
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

        # track excursions while in position (exit bar's extremes count too)
        if self.pos != 0:
            self.hi = max(self.hi, bar.High)
            self.lo = min(self.lo, bar.Low)

        if mend == 960:                            # EOD: close out at final bar close
            if self.pos != 0:
                self._emit(d, self.pos, self.entry, bar.Close, "eod")
                self.pos = 0
            return
        if mend < 572:                             # act from the 9:31 candle close
            return

        if self.pos == 0:
            if not self.traded:
                if bar.Close > up:
                    self.pos, self.entry, self.traded = 1, bar.Close, True
                    self.hi = self.lo = self.entry
                elif bar.Close < dn:
                    self.pos, self.entry, self.traded = -1, bar.Close, True
                    self.hi = self.lo = self.entry
        elif self.pos == 1 and bar.Close < dn:
            self._emit(d, 1, self.entry, bar.Close, "band")
            self.pos = 0
        elif self.pos == -1 and bar.Close > up:
            self._emit(d, -1, self.entry, bar.Close, "band")
            self.pos = 0

    def OnEndOfAlgorithm(self):
        self.Log(f"MFE_TAGS={self.n_tags}")
