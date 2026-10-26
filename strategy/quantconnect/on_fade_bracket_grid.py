# region imports
from AlgorithmImports import *
# endregion

# ON fade bracket plateau test: same as on_level_fade_first_hit, but
# with a WIDE bracket grid to test whether B=15 is a plateau or a spike.
# Grid: B in {8, 10, 12, 13, 14, 15, 16, 17, 18, 20, 25}  (11 values)
# Emits per day: touch flags/entries for H,L,M plus res for all 11 B values.

BRACKETS = (8.0, 10.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 20.0, 25.0)


class NQOnFadeBracketGrid(QCAlgorithm):

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
        self.n_tags = 0
        self.on_h = None; self.on_l = None
        self.cur_date = None
        self._reset_rth()

    def _reset_rth(self):
        self.rth_open = None
        self.onh = None; self.onl = None; self.onm = None
        self.st = {"H": None, "L": None, "M": None}
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
                tp = entry + B; sl = entry - B
            else:
                tp = entry - B; sl = entry + B
            b_state[B] = dict(tp=tp, sl=sl, res=None)
        self.st[key] = dict(entry=entry, dr=dr, br=b_state)

    def OnData(self, slice: Slice):
        bar = slice.Bars.get(self.cont) if slice.Bars is not None else None
        if bar is None: return
        t = self.Time; d = t.date()
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
            self.onh = self.on_h; self.onl = self.on_l
            self.onm = (self.onh + self.onl) / 2.0
            self.on_h = None; self.on_l = None

        if not in_rth or self.rth_open is None: return
        self.rth_close = bar.Close

        if self.st["H"] is None:
            if bar.High >= self.onh:
                self._init_level("H", self.onh, -1); self._process_bar(bar, "H")
        else:
            self._process_bar(bar, "H")

        if self.st["L"] is None:
            if bar.Low <= self.onl:
                self._init_level("L", self.onl, +1); self._process_bar(bar, "L")
        else:
            self._process_bar(bar, "L")

        if self.st["M"] is None and (bar.High >= self.onm and bar.Low <= self.onm):
            dr = 1 if self.rth_open > self.onm else (-1 if self.rth_open < self.onm else 0)
            if dr != 0:
                self._init_level("M", self.onm, dr); self._process_bar(bar, "M")
        elif self.st["M"] is not None:
            self._process_bar(bar, "M")

        if mend == 960 and not self.emitted_today:
            self._emit_day(bar_close=bar.Close); self.emitted_today = True

    def _process_bar(self, bar, key):
        st = self.st[key]
        if st is None: return
        dr = st["dr"]
        for B, bs in st["br"].items():
            if bs["res"] is not None: continue
            tp = bs["tp"]; sl = bs["sl"]
            if dr == 1:
                tp_hit = bar.High >= tp; sl_hit = bar.Low <= sl
            else:
                tp_hit = bar.Low <= tp; sl_hit = bar.High >= sl
            if tp_hit and sl_hit: bs["res"] = "B"
            elif tp_hit: bs["res"] = "T"
            elif sl_hit: bs["res"] = "S"

    def _emit_day(self, bar_close):
        if self.rth_open is None or self.onh is None: return
        # ONE tag per LEVEL per DAY to keep tag under 512 char limit
        for key in ("H", "L", "M"):
            st = self.st[key]
            if st is None: continue
            parts = ["OG", key, self.cur_date.strftime("%Y-%m-%d"),
                     f"{st['entry']:.2f}", str(st["dr"]),
                     f"{self.rth_open:.2f}", f"{bar_close:.2f}"]
            for B in BRACKETS:
                r = st["br"][B]["res"]
                parts.append(r if r else "E")
            self._emit(",".join(parts))

    def OnEndOfAlgorithm(self):
        self.Log(f"OG_TAGS={self.n_tags}")
