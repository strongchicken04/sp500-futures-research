# region imports
from AlgorithmImports import *
# endregion

# NQ/ES intradenni spread mean-reversion (close-based od zacatku).
# Spread s(t) = (NQ_c/NQ_930) / (ES_c/ES_930) - 1 v bps (equal notional 1:1).
# Pro prahy X v THRESH: prvni 1m close s |s| >= X od 9:35 -> fade
# (side = sign(s); pnl fade = -side * (s_exit - s_entry)).
# Close-based rozhodnuti: TP = s zpet na 0 (close), stop = |s| >= X + S
# pro S v STOPS, jinak EOD. Zaznamename i max adverse extenzi a EOD hold.
# Tag: SP,date,X,side,tmin,adv,hit0,p20,p40,eod   (vse bps spreadu, gross)

THRESH = (10.0, 20.0, 30.0, 40.0, 60.0)
STOPS = (20.0, 40.0)


class NQESSpread(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2018, 1, 1)
        self.SetEndDate(2025, 12, 31)
        self.SetCash(1_000_000)
        nq = self.AddFuture(Futures.Indices.NASDAQ_100_E_MINI, Resolution.Minute,
                            dataNormalizationMode=DataNormalizationMode.Raw,
                            dataMappingMode=DataMappingMode.OpenInterest,
                            contractDepthOffset=0, extendedMarketHours=True)
        nq.SetFilter(0, 120)
        es = self.AddFuture(Futures.Indices.SP_500_E_MINI, Resolution.Minute,
                            dataNormalizationMode=DataNormalizationMode.Raw,
                            dataMappingMode=DataMappingMode.OpenInterest,
                            contractDepthOffset=0, extendedMarketHours=True)
        es.SetFilter(0, 120)
        self.nqf, self.esf = nq, es
        self.nq, self.es = nq.Symbol, es.Symbol
        self.cur_date = None
        self.n_tags = 0
        self._reset_day()

    def _reset_day(self):
        self.nq0 = None
        self.es0 = None
        self.st = {x: None for x in THRESH}

    def _emit(self, tag):
        try:
            sym = self.nqf.Mapped
            if sym is not None and sym in self.Securities and self.Securities[sym].Price > 0:
                tkt = self.LimitOrder(sym, 1, round(self.Securities[sym].Price * 0.5, 2), tag=tag)
                tkt.Cancel()
                self.n_tags += 1
        except Exception as e:
            self.Debug(f"tag fail: {e}")

    def OnData(self, slice: Slice):
        nqb = slice.Bars.get(self.nq) if slice.Bars is not None else None
        esb = slice.Bars.get(self.es) if slice.Bars is not None else None
        if nqb is None or esb is None:
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
        if self.nq0 is None:
            self.nq0, self.es0 = nqb.Close, esb.Close
            return
        s = ((nqb.Close / self.nq0) / (esb.Close / self.es0) - 1.0) * 1e4

        for x in THRESH:
            state = self.st[x]
            if state is None:
                if mend < 576:
                    continue
                if abs(s) >= x:
                    self.st[x] = dict(side=1 if s > 0 else -1, s0=s, tmin=mend - 570,
                                      adv=0.0, hit0=False,
                                      pnl={S: None for S in STOPS})
            elif state != "done":
                side = state["side"]
                fade_pnl = -side * (s - state["s0"])       # bps spreadu
                ext = side * s - x                          # extenze za prah
                if ext > state["adv"]:
                    state["adv"] = ext
                tp_now = (side * s) <= 0.0                  # spread zpet na 0
                if tp_now:
                    state["hit0"] = True
                for S in STOPS:
                    if state["pnl"][S] is None:
                        if ext >= S:
                            state["pnl"][S] = fade_pnl      # stop exit na close
                        elif tp_now:
                            state["pnl"][S] = fade_pnl      # TP exit na close
                if mend == 960:
                    for S in STOPS:
                        if state["pnl"][S] is None:
                            state["pnl"][S] = fade_pnl
                    self._emit(f"SP,{d.strftime('%Y-%m-%d')},{x:.0f},{side},{state['tmin']},"
                               f"{state['adv']:.1f},{int(state['hit0'])},"
                               f"{state['pnl'][20.0]:.1f},{state['pnl'][40.0]:.1f},{fade_pnl:.1f}")
                    self.st[x] = "done"

    def OnEndOfAlgorithm(self):
        self.Log(f"SP_TAGS={self.n_tags}")
