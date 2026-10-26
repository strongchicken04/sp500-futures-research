# region imports
from AlgorithmImports import *
from collections import deque
# endregion
#
# PROP S7: Opening-gap fade, small gaps only.
#
# No peer-reviewed cost-inclusive backtest exists for this one -- the
# supporting numbers are practitioner studies (tradingstats.net's 2,791-session
# NQ sample puts median time-to-fill at 7 minutes for small gaps rising to
# 143 minutes for large ones, and fill rates decay with gap size). Treat the
# edge as unproven until this backtest says otherwise.
#
# It earns its place in the queue on shape rather than evidence: high hit rate
# with a hard small stop is the cushion-builder the consistency rule demands,
# since that rule caps the single best day at half of total profit and so
# rewards many modest green days over one large one.
#
# It is also the mirror of gap-and-go, which failed at 17% pass in earlier
# testing -- weak evidence that the edge sits on the fade side.
#
# Rule: only fade gaps that are big enough to mean something and small enough
# to close. Require the gap to be under 40% of 20-day ATR, wait until 09:45
# for the open to stop extending, then fade toward the prior close.
#
# Tag: S7,datetime,dir,gap_pct,entry,sl,tp,exit,reason,pnl

TF_MIN = 5
GAP_MIN = 0.0012         # 0.12% of price
GAP_MAX = 0.0045         # 0.45% of price
ATR_FRAC_MAX = 0.40      # gap must be < 40% of 20d ATR
EXTEND_MAX = 0.0015      # abandon if price ran 0.15% past the open
HARD_STOP_PTS = 20.0
MIN_EDGE_PTS = 10.0     # target must still be this far away at entry
TIME_STOP_ET = 12 * 60
SKIP_WED = True


class PropS7GapFade(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2018, 1, 1)
        self.SetEndDate(2025, 12, 31)
        self.SetCash(1_000_000)
        f = self.AddFuture(
            Futures.Indices.NASDAQ_100_E_MINI, Resolution.Minute,
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
        self.day_open = None
        self.day_hi = None
        self.day_lo = None
        self.ranges = deque(maxlen=20)
        self.day_range_hi = None
        self.day_range_lo = None
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

        if self.cur_date != d:
            if self.trade is not None:
                self._close(b['c'], 'EOD_roll')
            if self.last_close is not None:
                self.prev_close = self.last_close
            if self.day_range_hi is not None:
                self.ranges.append(self.day_range_hi - self.day_range_lo)
            self.cur_date = d
            self.day_dow = b['t'].weekday()
            self.day_open = None
            self.day_hi = None
            self.day_lo = None
            self.day_range_hi = None
            self.day_range_lo = None
            self.done_today = False

        in_rth = 9 * 60 + 30 <= em <= 16 * 60 - 1
        if not in_rth:
            return

        if self.day_open is None:
            self.day_open = b['o']
        self.day_hi = b['h'] if self.day_hi is None else max(self.day_hi, b['h'])
        self.day_lo = b['l'] if self.day_lo is None else min(self.day_lo, b['l'])
        self.day_range_hi = (b['h'] if self.day_range_hi is None
                             else max(self.day_range_hi, b['h']))
        self.day_range_lo = (b['l'] if self.day_range_lo is None
                             else min(self.day_range_lo, b['l']))

        if self.trade is not None:
            tr = self.trade
            if tr['dir'] == 1:
                if b['l'] <= tr['sl']:
                    self._close(tr['sl'], 'SL')
                    self.last_close = b['c']
                    return
                if b['h'] >= tr['tp']:
                    self._close(tr['tp'], 'TP')
                    self.last_close = b['c']
                    return
            else:
                if b['h'] >= tr['sl']:
                    self._close(tr['sl'], 'SL')
                    self.last_close = b['c']
                    return
                if b['l'] <= tr['tp']:
                    self._close(tr['tp'], 'TP')
                    self.last_close = b['c']
                    return
            if em >= TIME_STOP_ET:
                self._close(b['c'], 'TIME')
                self.last_close = b['c']
                return
            if em >= 15 * 60 + 55:
                self._close(b['c'], 'EOD')
                self.last_close = b['c']
                return

        if (self.trade is None and not self.done_today
                and em == 9 * 60 + 45
                and self.prev_close is not None
                and len(self.ranges) >= 10
                and not (SKIP_WED and self.day_dow == 2)):
            gap = (self.day_open - self.prev_close) / self.prev_close
            gap_pts = abs(self.day_open - self.prev_close)
            atr = sum(self.ranges) / len(self.ranges)
            # Entry is at 09:45 but the target is yesterday's close, so on a
            # gap that has already filled by then the target sits behind the
            # entry and the trade exits instantly at a loss booked as "TP".
            # That is what the first run did: 129 target exits against 66
            # winners. Require the fill to still be ahead and worth taking.
            remaining = ((b['c'] - self.prev_close) if gap > 0
                         else (self.prev_close - b['c']))
            if (GAP_MIN <= abs(gap) <= GAP_MAX
                    and gap_pts < ATR_FRAC_MAX * atr
                    and remaining >= MIN_EDGE_PTS):
                # Abandon if the open kept running in the gap direction.
                if gap > 0:
                    extended = (self.day_hi - self.day_open) / self.day_open
                    if extended <= EXTEND_MAX:
                        self.trade = {
                            'dir': -1, 'entry': b['c'],
                            'sl': b['c'] + HARD_STOP_PTS,
                            'tp': self.prev_close, 'gap': gap,
                            'dt': b['t'].strftime('%Y-%m-%d %H:%M'),
                        }
                        self.done_today = True
                else:
                    extended = (self.day_open - self.day_lo) / self.day_open
                    if extended <= EXTEND_MAX:
                        self.trade = {
                            'dir': 1, 'entry': b['c'],
                            'sl': b['c'] - HARD_STOP_PTS,
                            'tp': self.prev_close, 'gap': gap,
                            'dt': b['t'].strftime('%Y-%m-%d %H:%M'),
                        }
                        self.done_today = True

        self.last_close = b['c']

    def _close(self, ex, reason):
        tr = self.trade
        pnl = tr['dir'] * (ex - tr['entry'])
        self._emit(f"S7,{tr['dt']},{tr['dir']},{tr['gap']*100:.3f},"
                   f"{tr['entry']:.2f},{tr['sl']:.2f},{tr['tp']:.2f},"
                   f"{ex:.2f},{reason},{pnl:.2f}")
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
