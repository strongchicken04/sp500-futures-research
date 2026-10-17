# region imports
from AlgorithmImports import *
# endregion
#
# PROP S6: Market intraday momentum, last-30-minute leg.
#
# Baltussen, Da, Lammers & Martens, "Hedging Demand and Market Intraday
# Momentum", Journal of Financial Economics 142(1) 2021 (SSRN 3760365).
# 60+ futures, 1974-2020. NQ coefficient 6.36, t = 7.97, adj R^2 4.10% --
# one of the strongest instruments in their sample. The mechanism is
# mechanical rather than behavioural: dealer gamma hedging plus leveraged-ETF
# rebalancing, both of which concentrate in the closing half hour and have
# grown over time.
#
# Rule: at 15:30 ET measure return-on-day against the prior session close.
# Beyond a threshold, take the same direction into the close.
#
# Only 29 minutes of exposure per day, so the worst case is one closing-range
# move and the loss is hard-capped. That bounded left tail is what makes it
# worth carrying on a trailing-drawdown account.
#
# The short leg is the decorrelated one: long-only ORB already owns the
# upside of a strong trend day, so SHORT_ONLY defaults to True.
#
# Tag: S6,datetime,dir,rod_pct,entry,exit,reason,pnl

TF_MIN = 5
ROD_THRESH = 0.0020      # 0.20% move on the day to qualify
HARD_STOP_PTS = 35.0     # hard cap, not a volatility stop
SHORT_ONLY = True
SKIP_WED = True


class PropS6RodMomentum(QCAlgorithm):

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
            self.cur_date = d
            self.day_dow = b['t'].weekday()

        in_rth = 9 * 60 + 30 <= em <= 16 * 60 - 1
        if not in_rth:
            return

        if self.trade is not None:
            tr = self.trade
            if tr['dir'] == 1 and b['l'] <= tr['sl']:
                self._close(tr['sl'], 'SL')
                self.last_close = b['c']
                return
            if tr['dir'] == -1 and b['h'] >= tr['sl']:
                self._close(tr['sl'], 'SL')
                self.last_close = b['c']
                return
            if em >= 15 * 60 + 55:
                self._close(b['c'], 'EOD')
                self.last_close = b['c']
                return

        # Signal is read once, on the 15:30 bar.
        if (self.trade is None and em == 15 * 60 + 30
                and self.prev_close is not None
                and not (SKIP_WED and self.day_dow == 2)):
            rod = (b['c'] - self.prev_close) / self.prev_close
            direction = 0
            if rod <= -ROD_THRESH:
                direction = -1
            elif rod >= ROD_THRESH and not SHORT_ONLY:
                direction = 1
            if direction != 0:
                sl = (b['c'] - HARD_STOP_PTS if direction == 1
                      else b['c'] + HARD_STOP_PTS)
                self.trade = {
                    'dir': direction, 'entry': b['c'], 'sl': sl, 'rod': rod,
                    'dt': b['t'].strftime('%Y-%m-%d %H:%M'),
                }

        self.last_close = b['c']

    def _close(self, ex, reason):
        tr = self.trade
        pnl = tr['dir'] * (ex - tr['entry'])
        self._emit(f"S6,{tr['dt']},{tr['dir']},{tr['rod']*100:.3f},"
                   f"{tr['entry']:.2f},{ex:.2f},{reason},{pnl:.2f}")
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
