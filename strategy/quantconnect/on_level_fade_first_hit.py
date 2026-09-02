# region imports
from AlgorithmImports import *
# endregion

# ON level fade with HONEST intraday first-touch TP/SL tracking.
#
# For each RTH day (given ON range 18:00 prev - 9:30):
#   ONH = overnight high, ONL = overnight low, ONM = midpoint
# On FIRST touch of each level during RTH, initiate a fade trade:
#   ONH touch -> SHORT at ONH  (fading breakout up)
#   ONL touch -> LONG  at ONL  (fading breakout down)
#   ONM touch -> LONG if open > ONM (fade back to open from below)
#                SHORT if open < ONM (fade back to open from above)
#                (= expects mean reversion toward the day's opening bias)
# For each fade trade track FIRST-HIT of TP vs SL for 4 bracket sizes:
#   B in {10, 15, 20, 30} pts, 1:1 TP=SL=B
# Conservative: if TP and SL both in same 1-min bar -> SL.
# If neither hit by 15:59 -> EOD close.
#
# Tag per day: OF,date,onh,onl,onm,open,close,
#              tH,eH,resH10,resH15,resH20,resH30,
#              tL,eL,resL10,resL15,resL20,resL30,
#              tM,eM,dM,resM10,resM15,resM20,resM30
#   tX = 1 if touched, eX = entry price (or 0), dM = midpoint fade dir (+1/-1/0)
#   resX_B = "T" TP first / "S" SL first / "B" both same bar / "E" EOD / "N" no touch

BRACKETS = (10.0, 15.0, 20.0, 30.0)


class NQOnLevelFadeFirstHit(QCAlgorithm):

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
        self.n_tags = 0

        self.on_h = None
        self.on_l = None
        self.cur_date = None
        self._reset_rth()

    def _reset_rth(self):
        self.rth_open = None
        self.onh = None
        self.onl = None
        self.onm = None
        # per-level per-bracket state
        self.st = {"H": None, "L": None, "M": None}
        # each st is dict(entry, dir, brackets={B: {res, tp, sl}})
        self.rth_close = None
        self.emitted_today = False

    def _emit(self, tag):
        try:
            sym = self.future.Mapped
            if sym is not None and sym in self.Securities and self.Securities[sym].Price > 0:
                tkt = self.LimitOrder(sym, 1, round(self.Securities[sym].Price * 0.5, 2), tag=tag)
                tkt.Cancel()
                self.n_tags += 1
        except Exception as e:
            self.Debug(f"tag fail: {e}")

    def _init_level(self, key, entry, dr):
        b_state = {}
        for B in BRACKETS:
            if dr == 1:
                tp = entry + B
                sl = entry - B
            else:
                tp = entry - B
                sl = entry + B
            b_state[B] = dict(tp=tp, sl=sl, res=None)
        self.st[key] = dict(entry=entry, dr=dr, br=b_state)

    def OnData(self, slice: Slice):
        bar = slice.Bars.get(self.cont) if slice.Bars is not None else None
        if bar is None:
            return

        t = self.Time
        d = t.date()
        mend = t.hour * 60 + t.minute
        in_on = (mend >= 1080) or (mend <= 570)
        in_rth = 571 <= mend <= 960

        if in_on:
            if self.on_h is None:
                self.on_h = bar.High; self.on_l = bar.Low
            else:
                self.on_h = max(self.on_h, bar.High); self.on_l = min(self.on_l, bar.Low)

        if self.cur_date is None:
            self.cur_date = d
        elif d != self.cur_date:
            if not self.emitted_today:
                self._emit_day(bar_close=(self.rth_close if self.rth_close else bar.Close))
            self._reset_rth()
            self.cur_date = d

        if mend == 571 and self.rth_open is None and self.on_h is not None:
            self.rth_open = bar.Open
            self.onh = self.on_h
            self.onl = self.on_l
            self.onm = (self.onh + self.onl) / 2.0
            self.on_h = None
            self.on_l = None

        if not in_rth or self.rth_open is None:
            return

        self.rth_close = bar.Close

        # ---- detect first touch of each level ----
        # ONH touch: bar.High >= onh
        if self.st["H"] is None:
            if bar.High >= self.onh:
                # entry = ONH (assume perfect fill at level touch), SHORT (fade)
                self._init_level("H", self.onh, -1)
                # process this bar's post-touch progression too
                self._process_bar(bar, "H", first_bar_of_touch=True)
        else:
            self._process_bar(bar, "H", first_bar_of_touch=False)

        # ONL touch: bar.Low <= onl
        if self.st["L"] is None:
            if bar.Low <= self.onl:
                self._init_level("L", self.onl, +1)  # LONG fade
                self._process_bar(bar, "L", first_bar_of_touch=True)
        else:
            self._process_bar(bar, "L", first_bar_of_touch=False)

        # ONM touch: any bar crossing through onm
        # fade direction = toward open
        if self.st["M"] is None and (bar.High >= self.onm and bar.Low <= self.onm):
            if self.rth_open > self.onm:
                dr = 1        # LONG (back to open which is above)
            elif self.rth_open < self.onm:
                dr = -1       # SHORT (back to open which is below)
            else:
                dr = 0
            if dr != 0:
                self._init_level("M", self.onm, dr)
                self._process_bar(bar, "M", first_bar_of_touch=True)
        elif self.st["M"] is not None:
            self._process_bar(bar, "M", first_bar_of_touch=False)

        # RTH close: emit
        if mend == 960 and not self.emitted_today:
            self._emit_day(bar_close=bar.Close)
            self.emitted_today = True

    def _process_bar(self, bar, key, first_bar_of_touch):
        st = self.st[key]
        if st is None:
            return
        dr = st["dr"]
        for B, bstate in st["br"].items():
            if bstate["res"] is not None:
                continue
            tp = bstate["tp"]; sl = bstate["sl"]
            if dr == 1:
                tp_hit = bar.High >= tp
                sl_hit = bar.Low <= sl
            else:
                tp_hit = bar.Low <= tp
                sl_hit = bar.High >= sl
            if tp_hit and sl_hit:
                bstate["res"] = "B"
            elif tp_hit:
                bstate["res"] = "T"
            elif sl_hit:
                bstate["res"] = "S"

    def _emit_day(self, bar_close):
        if self.rth_open is None or self.onh is None:
            return
        parts = ["OF", self.cur_date.strftime("%Y-%m-%d"),
                 f"{self.onh:.2f}", f"{self.onl:.2f}", f"{self.onm:.2f}",
                 f"{self.rth_open:.2f}", f"{bar_close:.2f}"]

        for key in ("H", "L", "M"):
            st = self.st[key]
            if st is None:
                parts.extend(["0", "0"])
                if key == "M":
                    parts.append("0")
                for B in BRACKETS:
                    parts.append("N")
            else:
                parts.extend(["1", f"{st['entry']:.2f}"])
                if key == "M":
                    parts.append(str(st["dr"]))
                for B in BRACKETS:
                    r = st["br"][B]["res"]
                    parts.append(r if r else "E")
        self._emit(",".join(parts))

    def OnEndOfAlgorithm(self):
        self.Log(f"OF_TAGS={self.n_tags}")
