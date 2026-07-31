# region imports
from AlgorithmImports import *
from collections import deque
import math
# endregion

# Holmberg, Lonnbark & Lundstrom (Umea): "Assessing the profitability of
# intraday opening range breakout strategies" - replikace na NQ.
#
# Strategie: ORB s volatilitne skalovanym prahem rho = mu + sigma * z_alpha
# z rozdeleni dennich open->close log vynosu. Long pri P >= Po*exp(rho_long),
# short pri P <= Po*exp(rho_short). Exit na close (16:00), zadny SL.
#
# Nase verze je poctivejsi nez paper: prahy z ROLLING 250d okna (past-only,
# zadny in-sample look-ahead), minutova data, gap-safe fill na prahu
# (fill = max(prah, open baru) pro long). 5 hladin alpha bezi paralelne
# jako nezavisle knihy, 1 obchod/den/kniha (prvni dotek rozhoduje smer).
#
# Tag: HB,date,alpha_idx,dir,entry,close  (pnl dopocitame v analyze)

ALPHAS = [0.10, 0.05, 0.01, 0.005, 0.001]
ZS     = [1.2816, 1.6449, 2.3263, 2.5758, 3.0902]
WINDOW = 250
MIN_HIST = 60


class NQHolmbergORB(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2018, 1, 1)
        self.SetEndDate(2025, 12, 31)
        self.SetCash(1_000_000)
        f = self.AddFuture(
            Futures.Indices.NASDAQ100EMini, Resolution.Minute,
            dataNormalizationMode=DataNormalizationMode.Raw,
            dataMappingMode=DataMappingMode.OpenInterest,
            contractDepthOffset=0, extendedMarketHours=True)
        f.SetFilter(0, 120)
        self.future = f
        self.cont = f.Symbol
        self.rets = deque(maxlen=WINDOW)   # log(Pc/Po) minulych RTH dni
        self.cur_date = None
        self.n_tags = 0
        self._reset_day()

    def _reset_day(self):
        self.d_open = None
        self.d_close = None
        self.up = [None] * len(ALPHAS)     # prahy long
        self.dn = [None] * len(ALPHAS)     # prahy short
        self.book = [None] * len(ALPHAS)   # (dir, entry) po vstupu

    def _emit(self, tag):
        try:
            sym = self.future.Mapped
            if sym is not None and sym in self.Securities and self.Securities[sym].Price > 0:
                tkt = self.LimitOrder(sym, 1, round(self.Securities[sym].Price * 0.5, 2), tag=tag)
                tkt.Cancel()
                self.n_tags += 1
        except Exception as e:
            self.Debug(f"tag fail: {e}")

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

        if self.d_open is None:
            self.d_open = bar.Open
            if len(self.rets) >= MIN_HIST:
                mu = sum(self.rets) / len(self.rets)
                var = sum((x - mu) ** 2 for x in self.rets) / (len(self.rets) - 1)
                sd = math.sqrt(var)
                for i, z in enumerate(ZS):
                    self.up[i] = self.d_open * math.exp(mu + sd * z)
                    self.dn[i] = self.d_open * math.exp(mu - sd * z)
        self.d_close = bar.Close

        # vstupy (gap-safe fill), 1 obchod/den/kniha
        for i in range(len(ALPHAS)):
            if self.book[i] is not None or self.up[i] is None:
                continue
            hit_up = bar.High >= self.up[i]
            hit_dn = bar.Low <= self.dn[i]
            if hit_up and hit_dn:
                # oba prahy v jedne minute -> smer podle blizsiho k open baru
                mid_up = abs(bar.Open - self.up[i])
                mid_dn = abs(bar.Open - self.dn[i])
                hit_up, hit_dn = (mid_up <= mid_dn), (mid_up > mid_dn)
            if hit_up:
                self.book[i] = (1, max(self.up[i], bar.Open))
            elif hit_dn:
                self.book[i] = (-1, min(self.dn[i], bar.Open))

        # EOD: emit vsech knih + update historie vynosu
        if mend == 960:
            for i, b in enumerate(self.book):
                if b is not None:
                    self._emit(f"HB,{d.strftime('%Y-%m-%d')},{i},{b[0]},{b[1]:.2f},{bar.Close:.2f}")
            if self.d_open and self.d_open > 0 and bar.Close > 0:
                self.rets.append(math.log(bar.Close / self.d_open))

    def OnEndOfAlgorithm(self):
        self.Log(f"HB_TAGS={self.n_tags}")
