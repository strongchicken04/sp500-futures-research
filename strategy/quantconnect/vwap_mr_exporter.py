# region imports
from AlgorithmImports import *
# endregion

# VWAP mean-reversion mapovaci studie.
# Session VWAP (RTH, HLC3). Pro pasma X v BANDS (bps): prvni dotek dne
# (od 9:35), po doteku sledujeme do 15:59:
#   adv  = max dalsi extenze ZA pasmo v bps (proti fade obchodu)
#   hitV = dotkla se cena VWAPu po doteku pasma?
#   hitO = dosla az na opacne pasmo -X (full cross)?
#   eod  = PnL fade obchodu (vstup na urovni pasma pri doteku) do close, bps
#   tmin = minuta doteku po 9:30
# Tag na dotknute pasmo: MR,date,X,side,tmin,adv,hitV,hitO,eod

BANDS = (20.0, 30.0, 40.0, 60.0, 80.0, 100.0)


class NQVwapMR(QCAlgorithm):

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
        self.cur_date = None
        self.n_tags = 0
        self._reset_day()

    def _reset_day(self):
        self.cpv = 0.0
        self.cv = 0.0
        self.st = {x: None for x in BANDS}    # stav pasma po doteku

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

        hlc3 = (bar.High + bar.Low + bar.Close) / 3.0
        self.cpv += hlc3 * float(bar.Volume)
        self.cv += float(bar.Volume)
        if self.cv <= 0:
            return
        vwap = self.cpv / self.cv

        for x in BANDS:
            b = x / 1e4
            up = vwap * (1 + b)
            dn = vwap * (1 - b)
            s = self.st[x]
            if s is None:
                if mend < 576:                       # doteky az od 9:35
                    continue
                side = 0
                if bar.High >= up:
                    side = 1
                elif bar.Low <= dn:
                    side = -1
                if side != 0:
                    entry = up if side == 1 else dn
                    self.st[x] = dict(side=side, entry=entry, tmin=mend - 570,
                                      adv=0.0, hitV=False, hitO=False)
            elif s != "done":
                side = s["side"]
                if side == 1:
                    ext = (bar.High / vwap - 1.0) * 1e4 - x
                    if bar.Low <= vwap:
                        s["hitV"] = True
                    if bar.Low <= dn:
                        s["hitO"] = True
                else:
                    ext = (1.0 - bar.Low / vwap) * 1e4 - x
                    if bar.High >= vwap:
                        s["hitV"] = True
                    if bar.High >= up:
                        s["hitO"] = True
                if ext > s["adv"]:
                    s["adv"] = ext
                if mend == 960:
                    eod = (s["entry"] - bar.Close) / s["entry"] * 1e4 * side
                    self._emit(f"MR,{d.strftime('%Y-%m-%d')},{x:.0f},{side},{s['tmin']},"
                               f"{s['adv']:.1f},{int(s['hitV'])},{int(s['hitO'])},{eod:.1f}")
                    self.st[x] = "done"

    def OnEndOfAlgorithm(self):
        self.Log(f"MR_TAGS={self.n_tags}")
