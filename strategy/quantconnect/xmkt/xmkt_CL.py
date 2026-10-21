# region imports
from AlgorithmImports import *
# endregion
#
# CROSS-MARKET BRACKET EXPORTER: the same signal families that showed some
# edge on NQ, on another CME future, with that market's own day session.
#
#   PDL / PDH  first session minute touching the prior session's low / high
#   ONL / ONH  first session minute touching the overnight low / high
#   IBU / IBD  first 5m close above / below the first-hour range (after it)
#   NZU / NZD  first half-hour close outside the noise area (Zarattini 2024)
#   MDU / MDD  at MID, price 30 bp above / below the session VWAP
#
# Entry is the close of the signalling bar; from the next minute the first
# touch of every LEVELS bp move up and down is recorded until EOD.
# Tag layout is identical to cond_bracket_exporter (G,...), so the same
# scorers read it.

INST = "CL"
SPECS = {
    # ticker, session start, session end (bar-end minutes, ET), mid check
    "ES":  (Futures.Indices.SP500EMini, 9 * 60 + 30, 16 * 60, 12 * 60),
    "YM":  (Futures.Indices.Dow30EMini, 9 * 60 + 30, 16 * 60, 12 * 60),
    "RTY": (Futures.Indices.Russell2000EMini, 9 * 60 + 30, 16 * 60, 12 * 60),
    "GC":  (Futures.Metals.Gold, 8 * 60 + 20, 13 * 60 + 30, 11 * 60),
    "CL":  (Futures.Energies.CrudeOilWTI, 9 * 60, 14 * 60 + 30, 12 * 60),
    "ZN":  (Futures.Financials.Y10TreasuryNote, 8 * 60 + 20, 15 * 60, 11 * 60 + 30),
}
LEVELS = [5, 10, 15, 20, 25, 30, 40, 50, 60, 75, 100, 125, 150]


class XmktExporter(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2018, 1, 1)
        self.SetEndDate(2025, 12, 31)
        self.SetCash(1_000_000)
        self.n_tags = 0
        ticker, self.S0, self.S1, self.MID = SPECS[INST]
        self.EOD = self.S1 - 5
        self.LAST = self.S1 - 60
        self.fut = self.AddFuture(
            ticker, Resolution.Minute,
            dataNormalizationMode=DataNormalizationMode.Raw,
            dataMappingMode=DataMappingMode.OpenInterest,
            contractDepthOffset=0, extendedMarketHours=True)
        self.fut.SetFilter(0, 180)
        self.day = None
        self.trk = []
        self.pc = self.pdh = self.pdl = None
        self.on_h = self.on_l = None
        self.noise = {}
        self.closes = []
        self._reset()

    def _reset(self):
        self.o0 = None
        self.onh = self.onl = None
        self.ses_h = self.ses_l = None
        self.pv = self.vol = 0.0
        self.orh = self.orl = None
        self.ibh = self.ibl = None
        self.b5 = None
        self.done = set()

    def OnData(self, slice):
        if slice.Bars is None:
            return
        bar = slice.Bars.get(self.fut.Symbol)
        if bar is None:
            return
        t = self.Time
        hm = t.hour * 60 + t.minute          # bar end time, ET
        o, h, l, c, v = (float(bar.Open), float(bar.High), float(bar.Low),
                         float(bar.Close), float(bar.Volume))
        if self.day != t.date():
            for tr in self.trk:
                self._emit(tr)
            self.trk = []
            self.day = t.date()
            self._reset()
        self._track(h, l, c, hm)

        if hm > self.S1 or hm <= self.S0:
            if hm == self.S1 + 1 or self.on_h is None:
                self.on_h, self.on_l = h, l
            else:
                self.on_h, self.on_l = max(self.on_h, h), min(self.on_l, l)
            return
        if t.weekday() >= 5:
            return
        if hm == self.S0 + 1:
            self.o0 = o
            self.onh, self.onl = self.on_h, self.on_l
        if self.o0 is None:
            return
        self.ses_h = h if self.ses_h is None else max(self.ses_h, h)
        self.ses_l = l if self.ses_l is None else min(self.ses_l, l)
        self.pv += (h + l + c) / 3.0 * v
        self.vol += v
        vwap = self.pv / self.vol if self.vol > 0 else c
        if hm <= self.S0 + 15:
            self.orh = h if self.orh is None else max(self.orh, h)
            self.orl = l if self.orl is None else min(self.orl, l)
        if hm <= self.S0 + 60:
            self.ibh = h if self.ibh is None else max(self.ibh, h)
            self.ibl = l if self.ibl is None else min(self.ibl, l)

        mv = abs(c / self.o0 - 1.0)
        hist = self.noise.setdefault(hm, [])
        sigma = sum(hist) / len(hist) if len(hist) >= 14 else None
        hist.append(mv)
        if len(hist) > 14:
            hist.pop(0)

        if hm == self.S1:
            self.pc, self.pdh, self.pdl = c, self.ses_h, self.ses_l
            return
        if self.pc is None or hm > self.LAST:
            return

        b = self.b5
        if b is None:
            self.b5 = b = [h, l, c]
        else:
            b[0], b[1], b[2] = max(b[0], h), min(b[1], l), c
        bar5 = (hm - self.S0) % 5 == 0
        if bar5:
            self.b5 = None
        cl = b[2]

        if l <= self.pdl:
            self._first("PDL", hm, c, vwap)
        if h >= self.pdh:
            self._first("PDH", hm, c, vwap)
        if self.onl is not None and l <= self.onl:
            self._first("ONL", hm, c, vwap)
        if self.onh is not None and h >= self.onh:
            self._first("ONH", hm, c, vwap)
        if bar5 and hm > self.S0 + 60:
            if cl > self.ibh:
                self._first("IBU", hm, cl, vwap)
            if cl < self.ibl:
                self._first("IBD", hm, cl, vwap)
        if (hm - self.S0) % 30 == 0 and hm >= self.S0 + 30 and sigma is not None:
            if c > max(self.o0, self.pc) * (1.0 + sigma):
                self._first("NZU", hm, c, vwap)
            if c < min(self.o0, self.pc) * (1.0 - sigma):
                self._first("NZD", hm, c, vwap)
        if hm == self.MID:
            if c > vwap * 1.003:
                self._first("MDU", hm, c, vwap)
            if c < vwap * 0.997:
                self._first("MDD", hm, c, vwap)

    def _first(self, typ, hm, px, vwap):
        if typ in self.done:
            return
        self.done.add(typ)
        self.trk.append({
            "ctx": (f"G,{self.Time.strftime('%Y%m%d')},{typ},{hm},{px:.4f},{self.pc:.4f},"
                    f"{self.pdh:.4f},{self.pdl:.4f},{self.o0:.4f},"
                    f"{(self.onh or 0):.4f},{(self.onl or 0):.4f},{vwap:.4f},"
                    f"{(self.orh or 0):.4f},{(self.orl or 0):.4f}"),
            "e": px, "k": 0, "up": [-1] * len(LEVELS), "dn": [-1] * len(LEVELS), "last": 0.0})

    def _track(self, h, l, c, hm):
        keep = []
        for tr in self.trk:
            tr["k"] += 1
            e = tr["e"]
            for i, bp in enumerate(LEVELS):
                d = e * bp / 10000.0
                if tr["up"][i] < 0 and h - e >= d:
                    tr["up"][i] = tr["k"]
                if tr["dn"][i] < 0 and e - l >= d:
                    tr["dn"][i] = tr["k"]
            tr["last"] = c - e
            if self.EOD <= hm <= self.S1:
                self._emit(tr)
            else:
                keep.append(tr)
        self.trk = keep

    def _emit(self, tr):
        tag = (tr["ctx"] + "," + ",".join(str(x) for x in tr["up"]) + ","
               + ",".join(str(x) for x in tr["dn"]) + f",{tr['last']:.4f}")
        try:
            sym = self.fut.Mapped
            if sym is not None and sym in self.Securities:
                px = self.Securities[sym].Price
                if px > 0:
                    mpv = float(self.Securities[sym].SymbolProperties.MinimumPriceVariation)
                    tkt = self.LimitOrder(sym, 1, round(px * 0.5 / mpv) * mpv, tag=tag)
                    tkt.Cancel()
                    self.n_tags += 1
        except Exception as ex:
            self.Debug(f"tag fail: {ex}")

    def OnEndOfAlgorithm(self):
        self.Log(f"TAGS={self.n_tags}")
