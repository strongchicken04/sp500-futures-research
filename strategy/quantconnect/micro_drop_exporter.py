# region imports
from AlgorithmImports import *
from collections import deque
import math
# endregion
#
# MICRO-DROP REVERSAL, tracked on 1-minute bars.
#
# Rif & Utz (QREF 2021) find that about a third of an extreme 1-minute drop in
# liquid Nasdaq-100 names reverses in the next minute. Batch B tested this
# with a 1-minute trigger but 5-minute tracking, so the 5-minute bar that
# contained the drop -- including the pre-drop high -- was scored as if it
# came after entry. That produced an impossible +15 pt per trade.
#
# Here the signal fires on the close of the extreme minute and every
# subsequent minute is tracked on its own, so nothing before the fill can
# count. Both directions are recorded (drop -> long, spike -> short).
#
# Tag: U,<sig>,<yyyymmddHHMM>,<dir>,<entry>,<s x5>,<t x5>,<p5>,<p10>,<p20>
#   s/t = first minute (1-based) a %-stop/%-target is touched, -1 if never
#   pN  = direction-adjusted points N minutes after entry

STOP_PCT = [0.0003, 0.0005, 0.0008, 0.0012, 0.0020]
TGT_PCT = [0.0003, 0.0005, 0.0008, 0.0012, 0.0020]
SIGMA = 4.0
WINDOW = 7800      # about 20 RTH sessions of 1-minute returns
HOLD = 20


class MicroDropExporter(QCAlgorithm):

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
        self.rets = deque(maxlen=WINDOW)
        self.s1 = 0.0
        self.s2 = 0.0
        self.prev = None
        self.prev_date = None
        self.open = []
        self.fired = set()

    def OnData(self, slice):
        bar = slice.Bars.get(self.cont) if slice.Bars is not None else None
        if bar is None:
            return
        t = self.Time
        em = t.hour * 60 + t.minute       # bar end minute
        if not (9 * 60 + 31 <= em <= 16 * 60):
            return
        d = t.date()
        if d != self.prev_date:
            self.prev_date = d
            self.prev = None
            self.open = []
            self.fired = set()
        h, l, c = float(bar.High), float(bar.Low), float(bar.Close)

        keep = []
        for s in self.open:
            s['k'] += 1
            e = s['e']
            adv = (e - l) if s['dir'] == 1 else (h - e)
            fav = (h - e) if s['dir'] == 1 else (e - l)
            for i, p in enumerate(STOP_PCT):
                if s['sb'][i] < 0 and adv >= e * p:
                    s['sb'][i] = s['k']
            for i, p in enumerate(TGT_PCT):
                if s['tb'][i] < 0 and fav >= e * p:
                    s['tb'][i] = s['k']
            pnl = s['dir'] * (c - e)
            if s['k'] == 5:
                s['p5'] = pnl
            if s['k'] == 10:
                s['p10'] = pnl
            if s['k'] >= HOLD or em >= 15 * 60 + 59:
                s['p20'] = pnl
                if s['p5'] is None:
                    s['p5'] = pnl
                if s['p10'] is None:
                    s['p10'] = pnl
                self._emit_sig(s)
            else:
                keep.append(s)
        self.open = keep

        if self.prev is not None and self.prev > 0:
            r = c / self.prev - 1.0
            n = len(self.rets)
            if n >= 3000 and 9 * 60 + 36 <= em <= 15 * 60 + 30:
                mean = self.s1 / n
                sd = math.sqrt(max(self.s2 / n - mean * mean, 1e-14))
                if r < mean - SIGMA * sd and 'D' not in self.fired:
                    self._open('MDL', 1, c, t)
                elif r > mean + SIGMA * sd and 'U' not in self.fired:
                    self._open('MDS', -1, c, t)
            if n == WINDOW:
                old = self.rets[0]
                self.s1 -= old
                self.s2 -= old * old
            self.rets.append(r)
            self.s1 += r
            self.s2 += r * r
        self.prev = c

    def _open(self, name, direction, price, t):
        self.fired.add('D' if direction == 1 else 'U')
        self.open.append({
            'name': name, 'dir': direction, 'e': price, 'k': 0,
            'sb': [-1] * len(STOP_PCT), 'tb': [-1] * len(TGT_PCT),
            'p5': None, 'p10': None, 'p20': None,
            'dt': t.strftime('%Y%m%d%H%M'),
        })

    def _emit_sig(self, s):
        sb = ",".join(str(x) for x in s['sb'])
        tb = ",".join(str(x) for x in s['tb'])
        self._emit(f"U,{s['name']},{s['dt']},{s['dir']},{s['e']:.2f},"
                   f"{sb},{tb},{s['p5']:.2f},{s['p10']:.2f},{s['p20']:.2f}")

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
