# region imports
from AlgorithmImports import *
# endregion
#
# MULTI-SIGNAL EXPORTER: many candidate entries, one backtest.
#
# The account has a single compute node, so testing ideas one backtest at a
# time is the bottleneck. This computes several unrelated entry signals in one
# pass and, for each firing, records the first bar at which each candidate
# stop and target (as % of entry price) would have been touched, plus the
# 15:55 result. Any stop/target pair for any signal can then be priced
# offline and scored on prop-account pass rate.
#
# Every signal fires at most once per day, enters at the close of the
# triggering 5-minute bar, and is tracked from the next bar. Nothing is
# filtered by weekday or volatility here; that is done offline.
#
# Tag: M,<sig>,<yyyymmddHHMM>,<dir>,<entry>,<s x5>,<t x5>,<struct>,<eod>
#   s = first bar adverse move >= STOP_PCT[i], -1 if never
#   t = first bar favourable move >= TGT_PCT[i], -1 if never
#   struct = first bar the structural stop level is touched, -1 if never
#   eod = points at 15:55 (direction-adjusted)

TF_MIN = 5
STOP_PCT = [0.0003, 0.0005, 0.0008, 0.0012, 0.0020]
TGT_PCT = [0.0005, 0.0010, 0.0020, 0.0035, 0.0060]
EOD_ET = 15 * 60 + 55


class MultiSignalExporter(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2018, 1, 1)
        self.SetEndDate(2025, 12, 31)
        self.SetCash(1_000_000)
        f = self.AddFuture(
            Futures.Indices.NASDAQ100EMini, Resolution.Minute,
            dataNormalizationMode=DataNormalizationMode.Raw,
            dataMappingMode=DataMappingMode.OpenInterest,
            contractDepthOffset=0, extendedMarketHours=True)
        f.SetFilter(0, 180)
        self.future = f
        self.cont = f.Symbol
        self.n_tags = 0
        self.bo = None
        self.bh = None
        self.bl = None
        self.bc = None
        self.bv = 0.0
        self.bstart = None
        self.cur_date = None
        # prior RTH session
        self.pdh = None
        self.pdl = None
        self.pdc = None
        # running RTH session
        self.rh = None
        self.rl = None
        self.rc = None
        self.ropen = None
        # overnight (outside RTH) range feeding the next session
        self.onh = None
        self.onl = None
        self.today_onh = None
        self.today_onl = None
        self.orh = None
        self.orl = None
        self.vwap_pv = 0.0
        self.vwap_v = 0.0
        self.fired = set()
        self.flags = {}
        self.open_sigs = []

    def _bs(self, t):
        m = (t.minute // TF_MIN) * TF_MIN
        return t.replace(minute=m, second=0, microsecond=0)

    def OnData(self, slice):
        bar = slice.Bars.get(self.cont) if slice.Bars is not None else None
        if bar is None:
            return
        bs = self._bs(self.Time)
        if self.bstart != bs:
            if self.bo is not None:
                self._on_bar({'o': self.bo, 'h': self.bh, 'l': self.bl,
                              'c': self.bc, 'v': self.bv, 't': self.bstart})
            self.bo = bar.Open
            self.bh = bar.High
            self.bl = bar.Low
            self.bc = bar.Close
            self.bv = float(bar.Volume)
            self.bstart = bs
        else:
            self.bh = max(self.bh, bar.High)
            self.bl = min(self.bl, bar.Low)
            self.bc = bar.Close
            self.bv += float(bar.Volume)

    # ------------------------------------------------------------------
    def _new_rth_day(self, d):
        if self.rh is not None:
            self.pdh = self.rh
            self.pdl = self.rl
            self.pdc = self.rc
        self.cur_date = d
        self.rh = None
        self.rl = None
        self.rc = None
        self.ropen = None
        self.orh = None
        self.orl = None
        self.vwap_pv = 0.0
        self.vwap_v = 0.0
        self.fired = set()
        self.flags = {}
        self.today_onh = self.onh
        self.today_onl = self.onl
        self.onh = None
        self.onl = None
        # anything still open from yesterday never saw a 15:55 bar
        self.open_sigs = []

    def _on_bar(self, b):
        em = b['t'].hour * 60 + b['t'].minute
        in_rth = 9 * 60 + 30 <= em < 16 * 60
        if not in_rth:
            self.onh = b['h'] if self.onh is None else max(self.onh, b['h'])
            self.onl = b['l'] if self.onl is None else min(self.onl, b['l'])
            return

        d = b['t'].date()
        if self.cur_date != d:
            self._new_rth_day(d)

        if self.ropen is None:
            self.ropen = b['o']
        self.rh = b['h'] if self.rh is None else max(self.rh, b['h'])
        self.rl = b['l'] if self.rl is None else min(self.rl, b['l'])
        self.rc = b['c']
        if em < 9 * 60 + 45:
            self.orh = b['h'] if self.orh is None else max(self.orh, b['h'])
            self.orl = b['l'] if self.orl is None else min(self.orl, b['l'])
        tp = (b['h'] + b['l'] + b['c']) / 3.0
        vol = b['v'] if b['v'] > 0 else 1.0
        self.vwap_pv += tp * vol
        self.vwap_v += vol
        vwap = self.vwap_pv / self.vwap_v

        self._track(b, em)
        if em < EOD_ET - 5:
            self._signals(b, em, vwap)

    # ------------------------------------------------------------------
    def _track(self, b, em):
        keep = []
        for s in self.open_sigs:
            s['n'] += 1
            e = s['e']
            if s['dir'] == 1:
                adv = e - b['l']
                fav = b['h'] - e
                struct_hit = s['sl'] is not None and b['l'] <= s['sl']
            else:
                adv = b['h'] - e
                fav = e - b['l']
                struct_hit = s['sl'] is not None and b['h'] >= s['sl']
            for i, p in enumerate(STOP_PCT):
                if s['sb'][i] < 0 and adv >= e * p:
                    s['sb'][i] = s['n']
            for i, p in enumerate(TGT_PCT):
                if s['tb'][i] < 0 and fav >= e * p:
                    s['tb'][i] = s['n']
            if s['xb'] < 0 and struct_hit:
                s['xb'] = s['n']
            if em >= EOD_ET:
                self._emit_sig(s, s['dir'] * (b['c'] - e))
            else:
                keep.append(s)
        self.open_sigs = keep

    def _open(self, name, b, direction, struct_sl):
        if name in self.fired:
            return
        self.fired.add(name)
        self.open_sigs.append({
            'name': name, 'dir': direction, 'e': b['c'], 'n': 0,
            'sl': struct_sl,
            'sb': [-1] * len(STOP_PCT), 'tb': [-1] * len(TGT_PCT), 'xb': -1,
            'dt': b['t'].strftime('%Y%m%d%H%M'),
        })

    def _signals(self, b, em, vwap):
        c = b['c']
        fl = self.flags

        # 1-2. Prior-day low sweep and reclaim (long), high sweep and fail
        # (short). Price trades through yesterday's extreme, then a bar
        # closes back on the inside. Structural stop beyond the sweep.
        if self.pdl is not None:
            if b['l'] < self.pdl:
                fl['pdl_swept'] = True
                fl['pdl_ext'] = min(fl.get('pdl_ext', b['l']), b['l'])
            if fl.get('pdl_swept') and c > self.pdl and em >= 9 * 60 + 35:
                self._open('PDLR', b, 1, fl['pdl_ext'])
        if self.pdh is not None:
            if b['h'] > self.pdh:
                fl['pdh_swept'] = True
                fl['pdh_ext'] = max(fl.get('pdh_ext', b['h']), b['h'])
            if fl.get('pdh_swept') and c < self.pdh and em >= 9 * 60 + 35:
                self._open('PDHF', b, -1, fl['pdh_ext'])

        # 3-4. Overnight low sweep and reclaim, overnight high sweep and fail.
        if self.today_onl is not None:
            if b['l'] < self.today_onl:
                fl['onl_swept'] = True
                fl['onl_ext'] = min(fl.get('onl_ext', b['l']), b['l'])
            if fl.get('onl_swept') and c > self.today_onl:
                self._open('ONLR', b, 1, fl['onl_ext'])
        if self.today_onh is not None:
            if b['h'] > self.today_onh:
                fl['onh_swept'] = True
                fl['onh_ext'] = max(fl.get('onh_ext', b['h']), b['h'])
            if fl.get('onh_swept') and c < self.today_onh:
                self._open('ONHF', b, -1, fl['onh_ext'])

        # 5-6. Opening-range trap: a close outside the 15-minute range that
        # is undone within six bars. Failed breakdown -> long, failed
        # breakout -> short.
        if self.orh is not None and em >= 9 * 60 + 45:
            if c < self.orl and 'orl_out' not in fl:
                fl['orl_out'] = em
                fl['orl_ext'] = b['l']
            if 'orl_out' in fl:
                fl['orl_ext'] = min(fl['orl_ext'], b['l'])
                if c > self.orl and em - fl['orl_out'] <= 30:
                    self._open('ORTL', b, 1, fl['orl_ext'])
            if c > self.orh and 'orh_out' not in fl:
                fl['orh_out'] = em
                fl['orh_ext'] = b['h']
            if 'orh_out' in fl:
                fl['orh_ext'] = max(fl['orh_ext'], b['h'])
                if c < self.orh and em - fl['orh_out'] <= 30:
                    self._open('ORTS', b, -1, fl['orh_ext'])

        # 7. VWAP reclaim after a flush: price got 0.4% below VWAP, then a
        # bar closes back above VWAP before 14:00.
        if c < vwap * (1 - 0.004):
            fl['flushed'] = True
            fl['flush_ext'] = min(fl.get('flush_ext', b['l']), b['l'])
        if fl.get('flushed') and c > vwap and em < 14 * 60:
            self._open('VWRC', b, 1, fl['flush_ext'])

        # 8. Ten-o'clock reversal: first 30 minutes fell more than 0.3%,
        # and the 10:00-10:05 bar closes green -> long.
        if em == 10 * 60 and self.ropen is not None:
            if (c - self.ropen) / self.ropen < -0.003 and c > b['o']:
                self._open('T10R', b, 1, self.rl)

        # 9. Afternoon trend hold: at 13:00, price above VWAP and above the
        # day's open and in the top third of the day's range -> long to
        # the close.
        if em == 13 * 60 and self.ropen is not None and self.rh > self.rl:
            pos = (c - self.rl) / (self.rh - self.rl)
            if c > vwap and c > self.ropen and pos > 0.66:
                self._open('PM13', b, 1, None)

    # ------------------------------------------------------------------
    def _emit_sig(self, s, eod_pts):
        sb = ",".join(str(x) for x in s['sb'])
        tb = ",".join(str(x) for x in s['tb'])
        self._emit(f"M,{s['name']},{s['dt']},{s['dir']},{s['e']:.2f},"
                   f"{sb},{tb},{s['xb']},{eod_pts:.2f}")

    def _emit(self, tag):
        try:
            sym = self.future.Mapped
            if sym is not None and sym in self.Securities:
                px = self.Securities[sym].Price
                if px > 0:
                    tkt = self.LimitOrder(sym, 1, round(px * 0.5, 2),
                                          tag=tag)
                    tkt.Cancel()
                    self.n_tags += 1
        except Exception as e:
            self.Debug(f"tag fail: {e}")

    def OnEndOfAlgorithm(self):
        self.Log(f"TAGS={self.n_tags}")
