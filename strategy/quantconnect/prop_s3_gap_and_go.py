# region imports
from AlgorithmImports import *
# endregion
#
# PROP S3: Gap-and-go continuation.
# At 09:30 ET: gap = open - prior_RTH_close. If |gap|/prior_close > 0.4%
# AND same sign as prior day (close - open):
#   enter market at open in gap direction
#   SL = prior day close ("gap fill")
#   TP = 2x gap size; otherwise EOD close
# Skip Wed, max 1 trade/day.
# Tag: S3,date,dir,entry,sl,tp,exit,reason,pnl,gap_pct

TF_MIN = 5


class PropS3GapGo(QCAlgorithm):

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
        self.bar_o = None; self.bar_h = None; self.bar_l = None
        self.bar_c = None; self.bar_start = None
        self.cur_date = None; self.day_dow = None
        self.day_open = None; self.day_high = None; self.day_low = None
        self.prev_rth_close = None; self.prev_rth_open = None
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
            # store prior day open/close for next day's gap calc
            if self.day_open is not None:
                self.prev_rth_close = self.day_c_last
                self.prev_rth_open = self.day_open
            self.cur_date = d
            self.day_dow = b['t'].weekday()
            self.day_open = None
            if self.trade is not None:
                self._close(b['c'], 'EOD_roll', b)

        in_rth = 9*60+30 <= em <= 16*60-1
        if not in_rth: return

        # mark day open at first RTH bar
        if self.day_open is None and em == 9*60+30:
            self.day_open = b['o']
            self.day_c_last = b['c']
            # entry check
            if (self.trade is None and self.day_dow != 2
                and self.prev_rth_close is not None and self.prev_rth_open is not None):
                gap = self.day_open - self.prev_rth_close
                gap_pct = abs(gap) / self.prev_rth_close
                prior_dir = 1 if self.prev_rth_close > self.prev_rth_open else -1
                gap_dir = 1 if gap > 0 else -1
                if gap_pct > 0.004 and gap_dir == prior_dir:
                    tp = self.day_open + 2 * gap  # 2x gap in gap dir
                    sl = self.prev_rth_close
                    self.trade = {'dir': gap_dir, 'entry': b['c'], 'sl': sl, 'tp': tp,
                                  'gap_pct': gap_pct, 'bars': 0,
                                  'dt': b['t'].strftime('%Y-%m-%d %H:%M')}
        # track running close
        self.day_c_last = b['c']

        # manage trade
        if self.trade is not None:
            tr = self.trade
            tr['bars'] += 1
            if tr['dir'] == 1:
                if b['l'] <= tr['sl']: self._close(tr['sl'], 'SL', b); return
                if b['h'] >= tr['tp']: self._close(tr['tp'], 'TP', b); return
            else:
                if b['h'] >= tr['sl']: self._close(tr['sl'], 'SL', b); return
                if b['l'] <= tr['tp']: self._close(tr['tp'], 'TP', b); return
            if em >= 15*60+55:
                self._close(b['c'], 'EOD', b); return

    def _close(self, ex, reason, b):
        tr = self.trade
        pnl = tr['dir'] * (ex - tr['entry'])
        self._emit(f"S3,{tr['dt']},{tr['dir']},{tr['entry']:.2f},"
                   f"{tr['sl']:.2f},{tr['tp']:.2f},{ex:.2f},{reason},"
                   f"{pnl:.2f},{tr['gap_pct']*100:.3f}")
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
        except Exception as e: self.Debug(f"tag fail: {e}")

    def OnEndOfAlgorithm(self):
        self.Log(f"TAGS={self.n_tags}")
