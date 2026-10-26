# region imports
from AlgorithmImports import *
from collections import deque
# endregion
#
# PROP S2: Event wait-and-break (FOMC/CPI/NFP proxy).
# Instead of hardcoded calendar, detect any 5m bar during 8:30-14:30 ET
# whose range > 1.8x 20-day avg first-RTH-bar range (news proxy).
# When found: mark that bar's h/l. Enter at close of next bar that closes
# beyond h/l in direction of close vs open of signal bar.
# SL = other side of signal bar. TP = 2.5x SL. EOD close. Max 1/day.
# Skip Wed.
#
# Tag: S2,date,dir,entry,sl,tp,exit,reason,pnl,sig_range

TF_MIN = 5


class PropS2EventBreak(QCAlgorithm):

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
        self.first_ranges = deque(maxlen=20)
        self.first_bar_range = None
        self.sig_bar = None  # candidate signal bar
        self.sig_bar_dir = 0  # +1 bull/-1 bear
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
            if self.first_bar_range is not None:
                self.first_ranges.append(self.first_bar_range)
            if self.trade is not None:
                self._close(b['c'], 'EOD_roll', b)
            self.cur_date = d
            self.day_dow = b['t'].weekday()
            self.first_bar_range = None
            self.sig_bar = None

        in_rth = 9*60+30 <= em <= 16*60-1
        if not in_rth: return

        bar_range = b['h'] - b['l']
        if em == 9*60+30:
            self.first_bar_range = bar_range

        # manage trade
        if self.trade is not None:
            tr = self.trade; tr['bars'] += 1
            if tr['dir'] == 1:
                if b['l'] <= tr['sl']: self._close(tr['sl'], 'SL', b); return
                if b['h'] >= tr['tp']: self._close(tr['tp'], 'TP', b); return
            else:
                if b['h'] >= tr['sl']: self._close(tr['sl'], 'SL', b); return
                if b['l'] <= tr['tp']: self._close(tr['tp'], 'TP', b); return
            if em >= 15*60+55: self._close(b['c'], 'EOD', b); return

        # look for signal: 5m bar with range > 1.8x 20d avg first-bar range
        if (self.trade is None and self.sig_bar is None and self.day_dow != 2
            and em >= 9*60+30 and em < 14*60+30 and len(self.first_ranges) >= 10):
            avg_range = sum(self.first_ranges) / len(self.first_ranges)
            if bar_range > 1.8 * avg_range and bar_range > 20:
                self.sig_bar = {'h':b['h'],'l':b['l'],'c':b['c'],'o':b['o']}
                self.sig_bar_dir = 1 if b['c'] > b['o'] else -1

        # entry: next bar after signal, close beyond signal h/l in direction of signal close
        if self.trade is None and self.sig_bar is not None:
            s = self.sig_bar
            s_range = s['h'] - s['l']
            if self.sig_bar_dir == 1 and b['c'] > s['h']:
                sl = s['l']; tp = b['c'] + 2.5 * s_range
                self.trade = {'dir':1,'entry':b['c'],'sl':sl,'tp':tp,'bars':0,
                              'sig_range':s_range,
                              'dt': b['t'].strftime('%Y-%m-%d %H:%M')}
                self.sig_bar = None
            elif self.sig_bar_dir == -1 and b['c'] < s['l']:
                sl = s['h']; tp = b['c'] - 2.5 * s_range
                self.trade = {'dir':-1,'entry':b['c'],'sl':sl,'tp':tp,'bars':0,
                              'sig_range':s_range,
                              'dt': b['t'].strftime('%Y-%m-%d %H:%M')}
                self.sig_bar = None

    def _close(self, ex, reason, b):
        tr = self.trade
        pnl = tr['dir'] * (ex - tr['entry'])
        self._emit(f"S2,{tr['dt']},{tr['dir']},{tr['entry']:.2f},"
                   f"{tr['sl']:.2f},{tr['tp']:.2f},{ex:.2f},{reason},"
                   f"{pnl:.2f},{tr['sig_range']:.2f}")
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
