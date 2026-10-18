# region imports
from AlgorithmImports import *
from collections import deque
# endregion
#
# PROP STRATEGY 1: ORB 15min long-only with runner (Zarattini 2024).
# At 09:45 ET mark OR high/low. Enter LONG at close of first 5m bar after
# 09:45 that closes above OR_high AND session VWAP.
# SL = OR_low (or 1x OR range below entry, closer). TP1 = +1R (close 50%,
# approximated by full close for simplicity). Runner = trail 20-EMA 5m.
# Max 1 trade/day. Skip Wed.
#
# Tag: S1,date,entry,sl,exit,reason,pnl,bars

TF_MIN = 5


class PropS1Orb15Long(QCAlgorithm):

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
        self.bar_o = None; self.bar_h = None; self.bar_l = None
        self.bar_c = None; self.bar_start = None
        self.cur_date = None; self.day_dow = None
        self.or_high = None; self.or_low = None; self.or_set = False
        self.vwap_pv = 0.0; self.vwap_v = 0.0
        self.ema20 = None; self.k20 = 2.0 / 21
        self.trade = None

    def _bs(self, t):
        m = (t.minute // TF_MIN) * TF_MIN
        return t.replace(minute=m, second=0, microsecond=0)

    def OnData(self, slice):
        bar = slice.Bars.get(self.cont) if slice.Bars is not None else None
        if bar is None: return
        bs = self._bs(self.Time)
        if self.bar_start != bs:
            if self.bar_o is not None:
                self._on_bar({'o':self.bar_o,'h':self.bar_h,'l':self.bar_l,
                              'c':self.bar_c,'t':self.bar_start})
            self.bar_o = bar.Open; self.bar_h = bar.High
            self.bar_l = bar.Low; self.bar_c = bar.Close; self.bar_start = bs
        else:
            self.bar_h = max(self.bar_h, bar.High)
            self.bar_l = min(self.bar_l, bar.Low)
            self.bar_c = bar.Close

    def _on_bar(self, b):
        em = b['t'].hour * 60 + b['t'].minute
        d = b['t'].date()
        if self.cur_date != d:
            if self.trade is not None:
                self._close(b['c'], 'EOD_roll', b)
            self.cur_date = d
            self.day_dow = b['t'].weekday()
            self.or_high = None; self.or_low = None; self.or_set = False
            self.vwap_pv = 0.0; self.vwap_v = 0.0
            self.ema20 = None

        in_rth = 9*60+30 <= em <= 16*60-1
        if not in_rth: return

        # update RTH VWAP
        hlc3 = (b['h'] + b['l'] + b['c']) / 3.0
        self.vwap_pv += hlc3; self.vwap_v += 1.0
        vwap = self.vwap_pv / self.vwap_v
        # 20-EMA 5m
        if self.ema20 is None:
            self.ema20 = b['c']
        else:
            self.ema20 = b['c'] * self.k20 + self.ema20 * (1 - self.k20)

        # Build OR 9:30-9:45 (3 5m bars)
        if em >= 9*60+30 and em < 9*60+45:
            if self.or_high is None:
                self.or_high = b['h']; self.or_low = b['l']
            else:
                self.or_high = max(self.or_high, b['h'])
                self.or_low = min(self.or_low, b['l'])
            return
        if em == 9*60+45 and not self.or_set:
            self.or_set = True

        # EOD flat
        if em >= 15*60+55 and self.trade is not None:
            self._close(b['c'], 'EOD', b); return

        # Manage trade: trail 20-EMA
        if self.trade is not None:
            tr = self.trade
            tr['bars'] += 1
            # SL hit
            if b['l'] <= tr['sl']:
                self._close(tr['sl'], 'SL', b); return
            # update trail stop: 20-EMA; move SL up only
            if self.ema20 is not None and self.ema20 > tr['sl']:
                tr['sl'] = self.ema20

        # Entry: Wed skip, OR must be set, long-only, close > OR_high AND > VWAP
        if (self.trade is None and self.or_set and self.day_dow == 2
            and b['c'] > self.or_high and b['c'] > vwap
            and em > 9*60+45 and em < 15*60):
            or_range = self.or_high - self.or_low
            sl_price = max(self.or_low, b['c'] - or_range)
            if sl_price >= b['c']: return
            self.trade = {'entry': b['c'], 'sl': sl_price, 'bars': 0,
                          'dt': b['t'].strftime('%Y-%m-%d %H:%M')}

    def _close(self, exit_px, reason, b):
        tr = self.trade
        pnl = exit_px - tr['entry']
        self._emit(f"S1,{tr['dt']},{tr['entry']:.2f},{tr['sl']:.2f},"
                   f"{exit_px:.2f},{reason},{pnl:.2f},{tr['bars']}")
        self.trade = None

    def _emit(self, tag):
        try:
            sym = self.future.Mapped
            if sym is not None and sym in self.Securities:
                px = self.Securities[sym].Price
                if px > 0:
                    tkt = self.LimitOrder(sym, 1, round(px*0.5, 2), tag=tag)
                    tkt.Cancel()
                    self.n_tags += 1
        except Exception as e:
            self.Debug(f"tag fail: {e}")

    def OnEndOfAlgorithm(self):
        self.Log(f"TAGS={self.n_tags}")
