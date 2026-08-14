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
#   r{S} = CLOSE-BASED rozhodnuti fade obchodu: vstup na CLOSE prvni svicky
#          s close za pasmem; TP = close svicky zpet za VWAPem (exit na tom
#          close); stop = close extenze >= S bps za pasmem (exit na tom
#          close); jinak EOD. Zadne knotove filly. r: 1=TP,0=stop,2=EOD.
#          eod{S} pole nese realny exit PnL v bps vuci entry-close.
# Tag: M3,date,X,side,tmin,adv,hitV,hitO,p20,p40,p60  (p = PnL bps net-of-nothing)

BANDS = (20.0, 30.0, 40.0, 60.0, 80.0, 100.0)
STOPS = (20.0, 40.0, 60.0)


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
                # close-based vstup: close svicky za pasmem
                if bar.Close >= up:
                    side = 1
                elif bar.Close <= dn:
                    side = -1
                else:
                    side = 0
                if side != 0:
                    self.st[x] = dict(side=side, entry=bar.Close, tmin=mend - 570,
                                      adv=0.0, hitV=False, hitO=False,
                                      pnl={s2: None for s2 in STOPS})
            elif s != "done":
                side = s["side"]
                # vse na CLOSE svicky
                ext_c = (bar.Close / vwap - 1.0) * 1e4 - x if side == 1 else (1.0 - bar.Close / vwap) * 1e4 - x
                tp_now = (bar.Close <= vwap) if side == 1 else (bar.Close >= vwap)
                if ext_c > s["adv"]:
                    s["adv"] = ext_c
                if tp_now:
                    s["hitV"] = True
                fade_pnl = (s["entry"] - bar.Close) / s["entry"] * 1e4 * side
                for s2 in STOPS:
                    if s["pnl"][s2] is None:
                        if ext_c >= s2:
                            s["pnl"][s2] = fade_pnl          # stop exit na close
                        elif tp_now:
                            s["pnl"][s2] = fade_pnl          # TP exit na close
                if mend == 960:
                    for s2 in STOPS:
                        if s["pnl"][s2] is None:
                            s["pnl"][s2] = fade_pnl          # EOD exit
                    self._emit(f"M3,{d.strftime('%Y-%m-%d')},{x:.0f},{side},{s['tmin']},"
                               f"{s['adv']:.1f},{int(s['hitV'])},{int(s['hitO'])},"
                               f"{s['pnl'][20.0]:.1f},{s['pnl'][40.0]:.1f},{s['pnl'][60.0]:.1f}")
                    self.st[x] = "done"

    def OnEndOfAlgorithm(self):
        self.Log(f"MR_TAGS={self.n_tags}")
