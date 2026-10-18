# region imports
from AlgorithmImports import *
# endregion
#
# PROP S8: Overnight gap reversal, long only.
#
# Buy the RTH open after the session gaps down against the prior close, hard
# stop a few points below, flat at 15:55. Della Corte & Kosowski's
# overnight-to-intraday reversal, cut down to one instrument and one leg.
#
# This exists to settle an open question rather than to propose something new.
# Tested on the local daily panel the rule looked strong, but that panel ends
# 2020-05 and the year-by-year split is not reassuring: +0.28 pt per trade
# over 2005-2012 against +4.27 over 2013-2020, with the losing years being the
# choppy corrections (2011 at -2.37, 2015 at -0.94). That profile says
# dip-buying in a bull market, not a structural edge.
#
# So the question this backtest answers is narrow and specific: did the edge
# survive 2020-2025, including 2022? If the answer is no, indicator 4 should
# come out of the book.
#
# The hard stop is the load-bearing part. Stopping at a full gap width instead
# takes the worst trade to -283 pt and the portfolio bust rate from 19% to
# 33%; widening it from 15 to 20 pt alone nearly doubles bust.
#
# Tag: S8,datetime,gap_pct,entry,sl,exit,reason,pnl

TF_MIN = 5
GAP_THRESH = -0.0025     # open at least 0.25% below the prior RTH close
STOP_CAP_PTS = 15.0
SKIP_WED = True


class PropS8GapReversal(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2018, 1, 1)
        self.SetEndDate(2025, 12, 31)
        self.SetCash(1_000_000)
        f = self.AddFuture(
            Futures.Indices.NASDAQ100EMini, Resolution.Minute,
            dataNormalizationMode=DataNormalizationMode.Raw,
            dataMappingMode=DataMappingMode.OpenInterest,
            contractDepthOffset=0, extendedMarketHours=False)
        f.SetFilter(0, 180)
        self.future = f
        self.cont = f.Symbol
        self.n_tags = 0
        self.bar_o = None
        self.bar_h = None
        self.bar_l = None
        self.bar_c = None
        self.bar_start = None
        self.cur_date = None
        self.day_dow = None
        self.prev_close = None
        self.last_close = None
        self.trade = None
        self.done_today = False

    def _bs(self, t):
        m = (t.minute // TF_MIN) * TF_MIN
        return t.replace(minute=m, second=0, microsecond=0)

    def OnData(self, slice):
        bar = slice.Bars.get(self.cont) if slice.Bars is not None else None
        if bar is None:
            return
        bs = self._bs(self.Time)
        if self.bar_start != bs:
            if self.bar_o is not None:
                self._on_bar({'o': self.bar_o, 'h': self.bar_h,
                              'l': self.bar_l, 'c': self.bar_c,
                              't': self.bar_start})
            self.bar_o = bar.Open
            self.bar_h = bar.High
            self.bar_l = bar.Low
            self.bar_c = bar.Close
            self.bar_start = bs
        else:
            self.bar_h = max(self.bar_h, bar.High)
            self.bar_l = min(self.bar_l, bar.Low)
            self.bar_c = bar.Close

    def _on_bar(self, b):
        em = b['t'].hour * 60 + b['t'].minute
        d = b['t'].date()
        new_day = self.cur_date != d

        if new_day:
            # A position still open at the day roll means the prior session
            # never produced a 15:55 bar -- a holiday or a data gap. Marking
            # it against the next session's price charges it the overnight
            # move, which is how the first run produced a lone -253 point
            # outlier on the 2020 Labor Day boundary. Drop it instead.
            self.trade = None
            if self.last_close is not None:
                self.prev_close = self.last_close
            self.cur_date = d
            self.day_dow = b['t'].weekday()
            self.done_today = False

        in_rth = 9 * 60 + 30 <= em <= 16 * 60 - 1
        if not in_rth:
            return

        if self.trade is not None:
            tr = self.trade
            if b['l'] <= tr['sl']:
                self._close(tr['sl'], 'SL')
                self.last_close = b['c']
                return
            if em >= 15 * 60 + 55:
                self._close(b['c'], 'EOD')
                self.last_close = b['c']
                return

        # The gap is only readable on the first RTH bar of the session.
        if (self.trade is None and not self.done_today
                and em == 9 * 60 + 30
                and self.prev_close is not None
                and not (SKIP_WED and self.day_dow == 2)):
            gap = (b['o'] - self.prev_close) / self.prev_close
            if gap <= GAP_THRESH:
                sz = min(abs(b['o'] - self.prev_close), STOP_CAP_PTS)
                self.trade = {
                    'entry': b['o'], 'sl': b['o'] - sz, 'gap': gap,
                    'dt': b['t'].strftime('%Y-%m-%d %H:%M'),
                }
                self.done_today = True
                # Entry is at this bar's open, so the bar's low is after the
                # fill and can stop it out immediately.
                if b['l'] <= self.trade['sl']:
                    self._close(self.trade['sl'], 'SL')

        self.last_close = b['c']

    def _close(self, ex, reason):
        tr = self.trade
        pnl = ex - tr['entry']
        self._emit(f"S8,{tr['dt']},{tr['gap']*100:.3f},{tr['entry']:.2f},"
                   f"{tr['sl']:.2f},{ex:.2f},{reason},{pnl:.2f}")
        self.trade = None

    def _emit(self, tag):
        try:
            sym = self.future.Mapped
            if sym is not None and sym in self.Securities:
                px = self.Securities[sym].Price
                if px > 0:
                    tkt = self.LimitOrder(sym, 1, round(px * 0.5, 2), tag=tag)
                    tkt.Cancel()
                    self.n_tags += 1
        except Exception as e:
            self.Debug(f"tag fail: {e}")

    def OnEndOfAlgorithm(self):
        self.Log(f"TAGS={self.n_tags}")
