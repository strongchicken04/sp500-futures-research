# region imports
from AlgorithmImports import *
# endregion

# VIX term structure exporter (regime feature test A).
#
# Kazdy den ~9:35 ET zaznamena:
#   vix  = VIX index (spot)
#   vx1  = cena predniho VX futures kontraktu, d1 = dni do expirace
#   vx2  = cena druheho kontraktu, d2 = dni do expirace
# Z toho lokalne: kontango slope (vx2/vx1), basis (vx1/vix), percentily.
# Zadne obchodovani; 1 tag/den pres NQ canceled limit order:
#   VX,date,vix,vx1,vx2,d1,d2

class NQVixTerm(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2018, 1, 1)
        self.SetEndDate(2025, 12, 31)
        self.SetCash(1_000_000)
        f = self.AddFuture(
            Futures.Indices.NASDAQ_100_E_MINI, Resolution.Minute,
            dataNormalizationMode=DataNormalizationMode.Raw,
            dataMappingMode=DataMappingMode.OpenInterest,
            contractDepthOffset=0, extendedMarketHours=True)
        f.SetFilter(0, 120)
        self.future = f
        self.cont = f.Symbol
        vx = self.AddFuture(Futures.Indices.VIX, Resolution.Minute)
        vx.SetFilter(0, 95)
        self.vx_sym = vx.Symbol
        self.vix = self.AddIndex("VIX", Resolution.Minute).Symbol
        self.cur_date = None
        self.done_today = False
        self.n_tags = 0

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
        t = self.Time
        d = t.date()
        if self.cur_date != d:
            self.cur_date = d
            self.done_today = False
        if self.done_today:
            return
        mend = t.hour * 60 + t.minute
        if mend < 575 or mend > 585:          # okno 9:35-9:45
            return

        chain = slice.FuturesChains.get(self.vx_sym) if slice.FuturesChains is not None else None
        if chain is None:
            return
        cons = sorted([c for c in chain if c.LastPrice > 0], key=lambda c: c.Expiry)
        if len(cons) < 2:
            return
        vx1, vx2 = cons[0], cons[1]
        d1 = (vx1.Expiry.date() - d).days
        d2 = (vx2.Expiry.date() - d).days
        if d1 < 0 or d2 <= d1:
            return
        vix_px = self.Securities[self.vix].Price if self.vix in self.Securities else 0.0
        tag = (f"VX,{d.strftime('%Y-%m-%d')},{vix_px:.2f},"
               f"{float(vx1.LastPrice):.2f},{float(vx2.LastPrice):.2f},{d1},{d2}")
        self._emit(tag)
        self.done_today = True

    def OnEndOfAlgorithm(self):
        self.Log(f"VX_TAGS={self.n_tags}")
