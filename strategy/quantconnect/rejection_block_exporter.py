# region imports
from AlgorithmImports import *
# endregion

# Rejection block (RB) kvalifikace a mereni odrazu - mechanicka verze.
#
# RB: 5m fraktalni pivot (2/2), zona = [telo, konec knotu] pivotni svicky.
#   bearish RB na pivot high: zona [max(o,c), h]; bullish zrcadlove.
# Kvalita (preregistrovano): wick_frac = knot/range >= 0.5 A sweep
#   (knot prestrelil max/min prechozich 12 5m baru, offset 3).
# Event = PRVNI navrat ceny do zony tyz den (high/low vstoupi do zony,
#   dokud zona nebyla prorazena close za knotem). Od CLOSE retest baru:
#   mfe = max priznivy pohyb ve smeru odmitnuti (z closes, bps)
#   pen = max prunik za telo smerem ke knotu (bps)
#   viol = 1 kdyz close prorazil za konec knotu (zona selhala)
#   Sledovani do violace nebo EOD. Zadne knotove filly.
# Tag: RB,date,side,tmin,wf,wbps,sweep,mfe,pen,viol

MIN_WICK_BPS = 2.0        # ignoruj pivoty s mikroskopickym knotem (pod sum)


class NQRejectionBlock(QCAlgorithm):

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
        self.b5 = []
        self.bucket = None
        self.o = self.h = self.l = self.c = None
        self.rbs = []          # aktivni rejection blocky

    def _emit(self, tag):
        try:
            sym = self.future.Mapped
            if sym is not None and sym in self.Securities and self.Securities[sym].Price > 0:
                tkt = self.LimitOrder(sym, 1, round(self.Securities[sym].Price * 0.5, 2), tag=tag)
                tkt.Cancel()
                self.n_tags += 1
        except Exception as e:
            self.Debug(f"tag fail: {e}")

    def _finish(self, rb, d):
        self._emit(f"RB,{d.strftime('%Y-%m-%d')},{rb['side']},{rb['tmin']},"
                   f"{rb['wf']:.2f},{rb['wbps']:.1f},{int(rb['sweep'])},"
                   f"{rb['mfe']:.1f},{rb['pen']:.1f},{int(rb['viol'])}")
        rb["state"] = "done"

    def _on_5m(self, d, mend, is_last):
        self.b5.append((self.o, self.h, self.l, self.c))
        n = len(self.b5)
        bar_o, bar_h, bar_l, bar_c = self.b5[-1]

        # ---- 1) update aktivnich RB (close-based mereni) ----
        for rb in self.rbs:
            if rb["state"] == "done":
                continue
            if rb["state"] == "wait":
                if rb["side"] == -1:                     # bearish: zona nahore
                    if bar_c > rb["wick_end"]:           # prorazeno bez retestu
                        rb["state"] = "done"
                        continue
                    if bar_h >= rb["body"]:              # retest zony
                        rb["state"] = "track"
                        rb["rc"] = bar_c
                        rb["tmin"] = mend - 570
                        if bar_c > rb["wick_end"]:
                            rb["viol"] = True
                            self._finish(rb, d)
                else:
                    if bar_c < rb["wick_end"]:
                        rb["state"] = "done"
                        continue
                    if bar_l <= rb["body"]:
                        rb["state"] = "track"
                        rb["rc"] = bar_c
                        rb["tmin"] = mend - 570
            elif rb["state"] == "track":
                rc = rb["rc"]
                if rb["side"] == -1:
                    fav = (rc - bar_c) / rc * 1e4
                    pen = (bar_c - rb["body"]) / rc * 1e4
                    violated = bar_c > rb["wick_end"]
                else:
                    fav = (bar_c - rc) / rc * 1e4
                    pen = (rb["body"] - bar_c) / rc * 1e4
                    violated = bar_c < rb["wick_end"]
                rb["mfe"] = max(rb["mfe"], fav)
                rb["pen"] = max(rb["pen"], pen)
                if violated:
                    rb["viol"] = True
                    self._finish(rb, d)
                elif is_last:
                    self._finish(rb, d)

        if is_last:
            for rb in self.rbs:
                if rb["state"] == "track":
                    self._finish(rb, d)
            return

        # ---- 2) novy pivot na indexu n-3 ----
        if n < 5:
            return
        i = n - 3
        hs = [b[1] for b in self.b5]
        ls = [b[2] for b in self.b5]
        o_, h_, l_, c_ = self.b5[i]
        rng = h_ - l_
        if rng <= 0:
            return
        if hs[i] > max(hs[i-2], hs[i-1], hs[i+1], hs[i+2]):
            wick = h_ - max(o_, c_)
            wbps = wick / h_ * 1e4
            if wbps >= MIN_WICK_BPS:
                lo_w = max(0, i - 15)
                sweep = i >= 5 and h_ > max(hs[lo_w:i-2])
                self.rbs.append(dict(side=-1, body=max(o_, c_), wick_end=h_,
                                     wf=wick / rng, wbps=wbps, sweep=sweep,
                                     state="wait", mfe=0.0, pen=0.0, viol=False, tmin=0))
        if ls[i] < min(ls[i-2], ls[i-1], ls[i+1], ls[i+2]):
            wick = min(o_, c_) - l_
            wbps = wick / l_ * 1e4
            if wbps >= MIN_WICK_BPS:
                lo_w = max(0, i - 15)
                sweep = i >= 5 and l_ < min(ls[lo_w:i-2])
                self.rbs.append(dict(side=1, body=min(o_, c_), wick_end=l_,
                                     wf=wick / rng, wbps=wbps, sweep=sweep,
                                     state="wait", mfe=0.0, pen=0.0, viol=False, tmin=0))

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
        bkt = (mend - 571) // 5
        if self.bucket is None:
            self.bucket = bkt
        if bkt != self.bucket:
            if self.o is not None:
                self._on_5m(d, mend, False)
            self.bucket = bkt
            self.o = self.h = self.l = self.c = None
        if self.o is None:
            self.o, self.h, self.l, self.c = bar.Open, bar.High, bar.Low, bar.Close
        else:
            self.h = max(self.h, bar.High)
            self.l = min(self.l, bar.Low)
            self.c = bar.Close
        if mend == 960 and self.o is not None:
            self._on_5m(d, mend, True)

    def OnEndOfAlgorithm(self):
        self.Log(f"RB_TAGS={self.n_tags}")
