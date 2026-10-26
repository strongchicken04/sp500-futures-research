# region imports
from AlgorithmImports import *
# endregion

# Premarket Range Sweep & Reclaim (strategie z videa #1)
#
# Pravidla:
#   1. Range = high/low okna 8:12-9:12 NY casu (premarket, extended hours data).
#   2. Po 9:12 cekame na sweep jedne strany range (high nebo low projede knotem).
#      Sweep HIGH -> hrajeme SHORT s targetem na LOW range (a naopak).
#   3. Vstup: prvni SILNA svicka v nasem smeru, ktera zavre ZPATKY UVNITR range
#      (silna = telo >= STRONG * rozsah svicky). Vstup na close teto svicky.
#   4. TP = protejsi strana range. SL = polovina vzdalenosti k TP (RR 2:1).
#   5. 1 obchod/den. Kdyz jsou pred vstupem sweepnute obe strany, den se rusi.
#      Kdyz cena dojde na target driv nez mame vstup, den se rusi. EOD flat 15:59.
#
# Realne ordery (market vstup + limit TP + stop SL u brokera, rucni OCO),
# 1 kontrakt NQ, $100k -> statistiky + equity primo z QC, per-trade data
# z order tagu pres API.

STRONG = 0.5          # telo >= 50 % rozsahu svicky
ENTRY_CUTOFF = 930    # posledni vstup 15:30 (minuta konce baru)
EOD = 959             # flat na close 15:58-59 svicky
R_START, R_END = 493, 552   # bary KONCICI 8:13..9:12 = okno 8:12-9:12


class NQSweepReclaim(QCAlgorithm):

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
        self._reset()

    def _reset(self):
        self.rh = None
        self.rl = None
        self.swept = 0        # 0 nic, -1 sweep high (short bias), +1 sweep low (long bias)
        self.dead = False
        self.traded = False
        self.pos = 0
        self.tp_t = None
        self.sl_t = None

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

    def _enter(self, side, px, d):
        sym = self.future.Mapped
        if sym is None or sym not in self.Securities or self.Securities[sym].Price <= 0:
            return
        tgt = self.rl if side == -1 else self.rh
        dist = abs(px - tgt)
        if dist <= 0:
            return
        slpx = self._tick(px + dist / 2.0 if side == -1 else px - dist / 2.0)
        tgt = self._tick(tgt)
        tag = (f"SR,{d.strftime('%Y-%m-%d')},{'S' if side == -1 else 'L'},"
               f"rng={self.rh - self.rl:.2f},e={px:.2f},tp={tgt:.2f},sl={slpx:.2f}")
        self.MarketOrder(sym, side, tag=tag)
        self.pos = side
        self.traded = True
        # bracket az PO market orderu (synchronni fill v backtestu)
        self.tp_t = self.LimitOrder(sym, -side, tgt, tag="TP")
        self.sl_t = self.StopMarketOrder(sym, -side, slpx, tag="SL")

    def OnOrderEvent(self, e):
        if e.Status != OrderStatus.Filled:
            return
        if self.tp_t is not None and e.OrderId == self.tp_t.OrderId:
            self._cancel(self.sl_t)
            self.pos = 0
        elif self.sl_t is not None and e.OrderId == self.sl_t.OrderId:
            self._cancel(self.tp_t)
            self.pos = 0

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
            self._reset()
        mend = t.hour * 60 + t.minute

        # 1) stavba range 8:12-9:12
        if R_START <= mend <= R_END:
            self.rh = bar.High if self.rh is None else max(self.rh, bar.High)
            self.rl = bar.Low if self.rl is None else min(self.rl, bar.Low)
            return
        if mend < R_START:
            return
        if self.rh is None or self.rl is None or self.rh <= self.rl:
            return

        # 2) EOD flat
        if mend >= EOD:
            if self.pos != 0 or self.Portfolio.Invested:
                self._flatten("EOD")
            return

        # 3) otevrena pozice -> exity resi resting ordery u brokera
        if self.pos != 0:
            return
        if self.dead or self.traded:
            return

        hi_sweep = bar.High > self.rh
        lo_sweep = bar.Low < self.rl

        # 4) detekce sweepu
        if self.swept == 0:
            if hi_sweep and lo_sweep:
                self.dead = True
                return
            if hi_sweep:
                self.swept = -1
            elif lo_sweep:
                self.swept = +1
            else:
                return
            # sweep svicka sama muze byt zaroven reclaim svicka -> pokracujeme

        rng = bar.High - bar.Low
        body_ok = rng > 0
        inside = self.rl < bar.Close < self.rh

        # 5) po sweepu: zruseni dne / vstup
        if self.swept == -1:
            if lo_sweep:                      # target dosazen bez nas
                self.dead = True
                return
            strong_bear = body_ok and bar.Close < bar.Open and (bar.Open - bar.Close) >= STRONG * rng
            if strong_bear and inside and mend <= ENTRY_CUTOFF:
                self._enter(-1, bar.Close, d)
        else:
            if hi_sweep:
                self.dead = True
                return
            strong_bull = body_ok and bar.Close > bar.Open and (bar.Close - bar.Open) >= STRONG * rng
            if strong_bull and inside and mend <= ENTRY_CUTOFF:
                self._enter(+1, bar.Close, d)
