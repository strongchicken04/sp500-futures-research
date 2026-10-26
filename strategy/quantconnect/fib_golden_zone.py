# region imports
from AlgorithmImports import *
# endregion

# Fibonacci "golden zone" + FVG confluence reversal (IG video #4)
#
# Pravidla (mechanizace):
#   1. 5m bary, RTH, intradenni pivoty (fractal 2/2).
#   2. Impuls: pivot LOW -> pozdejsi pivot HIGH (long; short zrcadlove),
#      range >= 0.15 % ceny.
#   3. Golden zone = retracement 0.618-0.79 impulsu.
#   4. Konfluence: behem impulsni nohy vznikl FVG (3-bar imbalance),
#      ktery se prekryva s golden zone.
#   5. Vstup: prvni 5m close uvnitr zony -> market ve smeru impulsu.
#      TP = extrem impulsu (fib "1" ve smeru obchodu), SL = opacny konec
#      (fib "0"). 1 obchod/den, vstupy do 15:30, EOD flat 15:59.
#   6. Setup zanika: nova extrema pred vstupem / prorazeni SL urovne.
#
# Realne ordery, 1 kontrakt NQ, $100k, 2018-2025.
# Tag vstupu: FB,date,dir,e=...,tp=...,sl=...,r=...

MIN_R_FRAC = 0.0015     # min velikost impulsu (0.15 % ceny)
Z_LO, Z_HI = 0.618, 0.79
ENTRY_CUTOFF = 930      # 15:30
EOD = 959


class NQFibGoldenZone(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2018, 1, 1)
        self.SetEndDate(2025, 12, 31)
        self.SetCash(100_000)
        f = self.AddFuture(
            Futures.Indices.NASDAQ_100_E_MINI, Resolution.Minute,
            dataNormalizationMode=DataNormalizationMode.Raw,
            dataMappingMode=DataMappingMode.OpenInterest,
            contractDepthOffset=0, extendedMarketHours=True)
        f.SetFilter(0, 120)
        self.future = f
        self.cont = f.Symbol
        self.cur_date = None
        self.tp_t = None
        self.sl_t = None
        self._reset_day()

    def _reset_day(self):
        self.b5 = []            # dokoncene 5m bary dne: (o,h,l,c)
        self.bucket = None
        self.o = self.h = self.l = self.c = None
        self.fvgs = []          # (lo, hi, bull, idx3)
        self.pl = None          # (price, idx) posledni pivot low
        self.ph = None
        self.pos = 0
        self.traded = False

    @staticmethod
    def _tick(px):
        return round(px * 4) / 4.0

    def _cancel(self, tkt):
        if tkt is not None and tkt.Status not in (OrderStatus.Filled, OrderStatus.Canceled, OrderStatus.Invalid):
            tkt.Cancel()

    def _flatten(self, why):
        self._cancel(self.tp_t)
        self._cancel(self.sl_t)
        if self.Portfolio.Invested:
            self.Liquidate(tag=why)
        self.pos = 0

    def OnOrderEvent(self, e):
        if e.Status != OrderStatus.Filled:
            return
        if self.tp_t is not None and e.OrderId == self.tp_t.OrderId:
            self._cancel(self.sl_t)
            self.pos = 0
        elif self.sl_t is not None and e.OrderId == self.sl_t.OrderId:
            self._cancel(self.tp_t)
            self.pos = 0

    def _on_5m(self, d):
        self.b5.append((self.o, self.h, self.l, self.c))
        n = len(self.b5)
        # FVG z poslednich 3 baru
        if n >= 3:
            b1, b3 = self.b5[n - 3], self.b5[n - 1]
            if b3[2] > b1[1]:
                self.fvgs.append((b1[1], b3[2], True, n - 1))
            if b3[1] < b1[2]:
                self.fvgs.append((b3[1], b1[2], False, n - 1))
        # pivoty s potvrzenim 2 bary (index n-3)
        if n >= 5:
            i = n - 3
            hs = [b[1] for b in self.b5]
            ls = [b[2] for b in self.b5]
            if hs[i] > max(hs[i-2], hs[i-1], hs[i+1], hs[i+2]):
                self.ph = (hs[i], i)
            if ls[i] < min(ls[i-2], ls[i-1], ls[i+1], ls[i+2]):
                self.pl = (ls[i], i)

    def _try_trade(self, d, mend):
        if self.traded or self.pos != 0 or mend > ENTRY_CUTOFF:
            return
        if self.pl is None or self.ph is None:
            return
        H, ih = self.ph
        L, il = self.pl
        R = H - L
        if R <= 0 or R < MIN_R_FRAC * H:
            return
        bar = self.b5[-1]
        if il < ih:
            # impuls nahoru -> long pullback
            if bar[1] > H or bar[2] < L:
                return                       # setup neplatny
            zlo, zhi = H - Z_HI * R, H - Z_LO * R
            if not any(b and hi >= zlo and lo <= zhi and il < i <= ih + 2
                       for lo, hi, b, i in self.fvgs):
                return
            if zlo <= bar[3] <= zhi:
                self._enter(1, bar[3], H, L, d)
        elif ih < il:
            # impuls dolu -> short pullback
            if bar[2] < L or bar[1] > H:
                return
            zlo, zhi = L + Z_LO * R, L + Z_HI * R
            if not any((not b) and hi >= zlo and lo <= zhi and ih < i <= il + 2
                       for lo, hi, b, i in self.fvgs):
                return
            if zlo <= bar[3] <= zhi:
                self._enter(-1, bar[3], L, H, d)

    def _enter(self, side, px, tp, sl, d):
        sym = self.future.Mapped
        if sym is None or sym not in self.Securities or self.Securities[sym].Price <= 0:
            return
        tag = (f"FB,{d.strftime('%Y-%m-%d')},{'L' if side == 1 else 'S'},"
               f"e={px:.2f},tp={tp:.2f},sl={sl:.2f},r={abs(tp - sl):.2f}")
        self.MarketOrder(sym, side, tag=tag)
        self.pos = side
        self.traded = True
        self.tp_t = self.LimitOrder(sym, -side, self._tick(tp), tag="TP")
        self.sl_t = self.StopMarketOrder(sym, -side, self._tick(sl), tag="SL")

    def OnData(self, slice: Slice):
        bar = slice.Bars.get(self.cont) if slice.Bars is not None else None
        if bar is None:
            return
        t = self.Time
        d = t.date()
        if self.cur_date is None:
            self.cur_date = d
        if d != self.cur_date:
            self.cur_date = d
            self._reset_day()

        mend = t.hour * 60 + t.minute
        if not (571 <= mend <= 960):
            return

        if mend >= EOD:
            if self.pos != 0 or self.Portfolio.Invested:
                self._flatten("EOD")
            return

        bkt = (mend - 571) // 5
        if self.bucket is None:
            self.bucket = bkt
        if bkt != self.bucket:
            if self.o is not None:
                self._on_5m(d)
                self._try_trade(d, mend)
            self.bucket = bkt
            self.o = self.h = self.l = self.c = None

        if self.o is None:
            self.o, self.h, self.l, self.c = bar.Open, bar.High, bar.Low, bar.Close
        else:
            self.h = max(self.h, bar.High)
            self.l = min(self.l, bar.Low)
            self.c = bar.Close
