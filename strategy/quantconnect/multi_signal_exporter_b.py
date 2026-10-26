# region imports
from AlgorithmImports import *
from collections import deque
import math
# endregion
#
# MULTI-SIGNAL EXPORTER, batch B.
#
# Same idea as batch A: several unrelated entries in one backtest, each
# firing at most once a day, with first-touch bars recorded for a grid of
# %-of-price stops and targets so everything is priced offline. Batch B adds
# per-signal time exits and records the structural stop's distance as well
# as the bar it was touched, which batch A omitted.
#
# Signals:
#   SWRL  sweep of min(prior-day low, overnight low) by 0.03-0.25% between
#         09:35 and 12:00, reclaimed by a 5m close within 3 bars -> long
#   SWRS  mirror at max(prior-day high, overnight high), 09:45-11:30,
#         time exit 13:00 -> short
#   CLML  selling climax: 5m bar makes a new session low on >=2.5x the
#         20-day volume for that slot, range >=1.5x slot average, closes in
#         the top 35% of its range; next bar trading above it -> long
#   CLMS  buying-climax mirror -> short
#   LMOL  15:25, prior-close-to-now return > 0.75x its 20-day mean absolute
#         value -> long into the close
#   LMOS  same, negative -> short into the close
#   PERL  30-minute slot whose 20-day mean return has t > 1.5 -> long for
#         that slot only
#   MDRP  1-minute return below -4 sigma of the trailing 20-day 1-minute
#         distribution -> long, 10-minute time exit
#
# Tag: B,<sig>,<yyyymmddHHMM>,<dir>,<entry>,<s x5>,<t x5>,<xb>,<pnl>,<xd>

TF_MIN = 5
STOP_PCT = [0.0003, 0.0005, 0.0008, 0.0012, 0.0020]
TGT_PCT = [0.0005, 0.0010, 0.0020, 0.0035, 0.0060]
EOD_ET = 15 * 60 + 55


class MultiSignalExporterB(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2018, 1, 1)
        self.SetEndDate(2025, 12, 31)
        self.SetCash(1_000_000)
        f = self.AddFuture(
            Futures.Indices.NASDAQ_100_E_MINI, Resolution.Minute,
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
        self.pdh = None
        self.pdl = None
        self.pdc = None
        self.rh = None
        self.rl = None
        self.rc = None
        self.onh = None
        self.onl = None
        self.today_onh = None
        self.today_onl = None
        self.fired = set()
        self.fl = {}
        self.open_sigs = []
        # per-5m-slot history of volume and range over the last 20 days
        self.slot_vol = {}
        self.slot_rng = {}
        # per-30m-slot history of returns
        self.half_ret = {}
        self.half_open = None
        self.half_key = None
        # |return to 15:25| history
        self.rod_abs = deque(maxlen=20)
        # 1-minute return distribution, about 20 RTH days
        self.m1 = deque(maxlen=7800)
        self.m1_sum = 0.0
        self.m1_sq = 0.0
        self.m1_prev = None
        self.prev_bar = None

    def _bs(self, t):
        m = (t.minute // TF_MIN) * TF_MIN
        return t.replace(minute=m, second=0, microsecond=0)

    def OnData(self, slice):
        bar = slice.Bars.get(self.cont) if slice.Bars is not None else None
        if bar is None:
            return
        self._minute(bar)
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
    def _minute(self, bar):
        t = self.Time
        em = t.hour * 60 + t.minute
        if not (9 * 60 + 31 <= em < 16 * 60):
            self.m1_prev = None
            return
        c = float(bar.Close)
        if self.m1_prev is not None and self.m1_prev > 0:
            r = c / self.m1_prev - 1.0
            n = len(self.m1)
            if n >= 3000 and 9 * 60 + 35 <= em <= 15 * 60 + 30:
                mean = self.m1_sum / n
                var = max(self.m1_sq / n - mean * mean, 1e-12)
                if r < mean - 4.0 * math.sqrt(var):
                    self._open_raw('MDRP', c, 1, None,
                                   t.strftime('%Y%m%d%H%M'), em + 10)
            if n == self.m1.maxlen:
                old = self.m1[0]
                self.m1_sum -= old
                self.m1_sq -= old * old
            self.m1.append(r)
            self.m1_sum += r
            self.m1_sq += r * r
        self.m1_prev = c

    def _new_rth_day(self, d):
        if self.rh is not None:
            self.pdh = self.rh
            self.pdl = self.rl
            self.pdc = self.rc
        self.cur_date = d
        self.rh = None
        self.rl = None
        self.rc = None
        self.fired = set()
        self.fl = {}
        self.today_onh = self.onh
        self.today_onl = self.onl
        self.onh = None
        self.onl = None
        self.open_sigs = []
        self.half_open = None
        self.half_key = None
        self.prev_bar = None

    def _on_bar(self, b):
        em = b['t'].hour * 60 + b['t'].minute
        if not (9 * 60 + 30 <= em < 16 * 60):
            self.onh = b['h'] if self.onh is None else max(self.onh, b['h'])
            self.onl = b['l'] if self.onl is None else min(self.onl, b['l'])
            return
        d = b['t'].date()
        if self.cur_date != d:
            self._new_rth_day(d)

        new_low = self.rl is not None and b['l'] < self.rl
        new_high = self.rh is not None and b['h'] > self.rh
        self.rh = b['h'] if self.rh is None else max(self.rh, b['h'])
        self.rl = b['l'] if self.rl is None else min(self.rl, b['l'])
        self.rc = b['c']

        self._track(b, em)
        if em < EOD_ET - 5:
            self._signals(b, em, new_low, new_high)
        self._update_history(b, em)
        self.prev_bar = b

    # ------------------------------------------------------------------
    def _track(self, b, em):
        keep = []
        for s in self.open_sigs:
            s['n'] += 1
            e = s['e']
            if s['dir'] == 1:
                adv = e - b['l']
                fav = b['h'] - e
                hit = s['sl'] is not None and b['l'] <= s['sl']
            else:
                adv = b['h'] - e
                fav = e - b['l']
                hit = s['sl'] is not None and b['h'] >= s['sl']
            for i, p in enumerate(STOP_PCT):
                if s['sb'][i] < 0 and adv >= e * p:
                    s['sb'][i] = s['n']
            for i, p in enumerate(TGT_PCT):
                if s['tb'][i] < 0 and fav >= e * p:
                    s['tb'][i] = s['n']
            if s['xb'] < 0 and hit:
                s['xb'] = s['n']
            if em >= min(s['xem'], EOD_ET):
                self._emit_sig(s, s['dir'] * (b['c'] - e))
            else:
                keep.append(s)
        self.open_sigs = keep

    def _open_raw(self, name, price, direction, sl, dt, exit_em):
        if name in self.fired:
            return
        self.fired.add(name)
        self.open_sigs.append({
            'name': name, 'dir': direction, 'e': price, 'n': 0, 'sl': sl,
            'sb': [-1] * len(STOP_PCT), 'tb': [-1] * len(TGT_PCT),
            'xb': -1, 'dt': dt, 'xem': exit_em,
        })

    def _open(self, name, b, direction, sl, exit_em=EOD_ET):
        self._open_raw(name, b['c'], direction, sl,
                       b['t'].strftime('%Y%m%d%H%M'), exit_em)

    def _signals(self, b, em, new_low, new_high):
        c = b['c']
        fl = self.fl

        # Sweep and reclaim of the lower of prior-day and overnight lows.
        lows = [x for x in (self.pdl, self.today_onl) if x is not None]
        if lows and 9 * 60 + 35 <= em <= 12 * 60:
            L = min(lows)
            depth = (L - b['l']) / L
            if 'swl_bar' not in fl and 0.0003 <= depth <= 0.0025:
                fl['swl_bar'] = em
                fl['swl_ext'] = b['l']
            if 'swl_bar' in fl:
                fl['swl_ext'] = min(fl['swl_ext'], b['l'])
                if c > L and em - fl['swl_bar'] <= 15:
                    self._open('SWRL', b, 1, fl['swl_ext'])
        highs = [x for x in (self.pdh, self.today_onh) if x is not None]
        if highs and 9 * 60 + 45 <= em <= 11 * 60 + 30:
            H = max(highs)
            depth = (b['h'] - H) / H
            if 'swh_bar' not in fl and 0.0003 <= depth <= 0.0025:
                fl['swh_bar'] = em
                fl['swh_ext'] = b['h']
            if 'swh_bar' in fl:
                fl['swh_ext'] = max(fl['swh_ext'], b['h'])
                if c < H and em - fl['swh_bar'] <= 15:
                    self._open('SWRS', b, -1, fl['swh_ext'], 13 * 60)

        # Climax reversals, confirmed by the following bar.
        slot = em
        if 'clm_sig' in fl and self.prev_bar is not None:
            sig = fl.pop('clm_sig')
            if sig[0] == 1 and b['h'] > sig[1]:
                self._open('CLML', b, 1, sig[2])
            if sig[0] == -1 and b['l'] < sig[1]:
                self._open('CLMS', b, -1, sig[2])
        vh = self.slot_vol.get(slot)
        rh_ = self.slot_rng.get(slot)
        if (vh is not None and len(vh) >= 15 and 10 * 60 <= em <= 14 * 60 + 30):
            av = sum(vh) / len(vh)
            ar = sum(rh_) / len(rh_)
            rng = b['h'] - b['l']
            if av > 0 and ar > 0 and rng > 0 and b['v'] >= 2.5 * av \
                    and rng >= 1.5 * ar:
                pos = (c - b['l']) / rng
                if new_low and pos >= 0.65:
                    fl['clm_sig'] = (1, b['h'], b['l'])
                elif new_high and pos <= 0.35:
                    fl['clm_sig'] = (-1, b['l'], b['h'])

        # Late-day momentum conditioned on the size of the move.
        if em == 15 * 60 + 25 and self.pdc is not None:
            rod = (c - self.pdc) / self.pdc
            if len(self.rod_abs) >= 15:
                thr = 0.75 * sum(self.rod_abs) / len(self.rod_abs)
                if rod > thr:
                    self._open('LMOL', b, 1, None)
                elif rod < -thr:
                    self._open('LMOS', b, -1, None)
            self.rod_abs.append(abs(rod))

        # Same-slot periodicity, long only, one slot per day.
        if (em - 9 * 60 - 30) % 30 == 0 and em <= 15 * 60:
            key = (em - 9 * 60 - 30) // 30
            hist = self.half_ret.get(key)
            if hist is not None and len(hist) >= 15:
                m = sum(hist) / len(hist)
                sd = math.sqrt(max(sum((x - m) ** 2 for x in hist)
                                   / (len(hist) - 1), 1e-12))
                tstat = m / (sd / math.sqrt(len(hist)))
                if tstat > 1.5:
                    self._open('PERL', b, 1, None, em + 30)

    def _update_history(self, b, em):
        self.slot_vol.setdefault(em, deque(maxlen=20)).append(b['v'])
        self.slot_rng.setdefault(em, deque(maxlen=20)).append(b['h'] - b['l'])
        key = (em - 9 * 60 - 30) // 30
        if self.half_key != key:
            if self.half_key is not None and self.half_open:
                r = self.prev_bar['c'] / self.half_open - 1.0 \
                    if self.prev_bar else 0.0
                self.half_ret.setdefault(self.half_key,
                                         deque(maxlen=20)).append(r)
            self.half_key = key
            self.half_open = b['o']

    # ------------------------------------------------------------------
    def _emit_sig(self, s, pnl):
        sb = ",".join(str(x) for x in s['sb'])
        tb = ",".join(str(x) for x in s['tb'])
        xd = abs(s['e'] - s['sl']) if s['sl'] is not None else -1
        self._emit(f"B,{s['name']},{s['dt']},{s['dir']},{s['e']:.2f},"
                   f"{sb},{tb},{s['xb']},{pnl:.2f},{xd:.2f}")

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
