# region imports
from AlgorithmImports import *
from collections import deque
# endregion
#
# PROP S5: NR4/NR7 volatility expansion.
# Compute daily range. If range of prior session is less than min of
# previous 4 daily ranges (NR4): mark that day's inside range.
# Next day: after 10:00 ET, enter on break of inside day's high (LONG)
# or low (SHORT). SL = other side of inside range (~40-60pt). TP = 3x SL
# or EOD. Skip Wed.
#
# Tag: S5,date,dir,entry,sl,tp,exit,reason,pnl

TF_MIN = 5
NR_LB = 4
MIN_SL_PTS = 15.0


class PropS5Nr4(QCAlgorithm):

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
        self.day_h = None; self.day_l = None
        self.daily_ranges = deque(maxlen=NR_LB+1)
        self.inside_hi = None; self.inside_lo = None
        self.setup_armed = False
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
            if self.day_h is not None:
                prev_range = self.day_h - self.day_l
                # NR4 check: prev day's range < min of last 4 ranges
                if len(self.daily_ranges) >= NR_LB:
                    recent4 = list(self.daily_ranges)[-NR_LB:]
                    if prev_range < min(recent4):
                        self.inside_hi = self.day_h; self.inside_lo = self.day_l
                        self.setup_armed = True
                    else:
                        self.setup_armed = False
                self.daily_ranges.append(prev_range)
            if self.trade is not None:
                self._close(b['c'], 'EOD_roll', b)
            self.cur_date = d
            self.day_dow = b['t'].weekday()
            self.day_h = b['h']; self.day_l = b['l']
            return

        in_rth = 9*60+30 <= em <= 16*60-1
        if in_rth:
            self.day_h = max(self.day_h, b['h']) if self.day_h else b['h']
            self.day_l = min(self.day_l, b['l']) if self.day_l else b['l']

        if not in_rth: return

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

        # entry: after 10:00 ET, armed setup, Wed skip
        if (self.trade is None and self.setup_armed and self.day_dow != 2
            and em >= 10*60 and em < 15*60+30
            and self.inside_hi is not None):
            if b['c'] > self.inside_hi:
                sl = max(self.inside_lo, b['c'] - 60.0)
                sl_dist = b['c'] - sl
                if sl_dist < MIN_SL_PTS: return
                tp = b['c'] + 3 * sl_dist
                self.trade = {'dir':1,'entry':b['c'],'sl':sl,'tp':tp,'bars':0,
                              'dt': b['t'].strftime('%Y-%m-%d %H:%M')}
                self.setup_armed = False
            elif b['c'] < self.inside_lo:
                sl = min(self.inside_hi, b['c'] + 60.0)
                sl_dist = sl - b['c']
                if sl_dist < MIN_SL_PTS: return
                tp = b['c'] - 3 * sl_dist
                self.trade = {'dir':-1,'entry':b['c'],'sl':sl,'tp':tp,'bars':0,
                              'dt': b['t'].strftime('%Y-%m-%d %H:%M')}
                self.setup_armed = False

    def _close(self, ex, reason, b):
        tr = self.trade
        pnl = tr['dir'] * (ex - tr['entry'])
        self._emit(f"S5,{tr['dt']},{tr['dir']},{tr['entry']:.2f},"
                   f"{tr['sl']:.2f},{tr['tp']:.2f},{ex:.2f},{reason},"
                   f"{pnl:.2f}")
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
