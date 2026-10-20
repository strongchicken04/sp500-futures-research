# region imports
from AlgorithmImports import *
# endregion
#
# CONDITIONAL BRACKET EXPORTER: real entry signals, every bracket shape.
#
# Each entry below records how far price travels both ways afterwards, so the
# direction, target and stop can be chosen offline, plus the context known at
# the moment of entry so that entries can be filtered offline:
#
#   MODE "A"  fixed times: T931, T1000, T1030, T1100
#   MODE "B"  ORB  first 5m close above the 09:30-09:45 high and VWAP
#             ORS  first 5m close below the 09:30-09:45 low and VWAP
#             VBU  first 5m close above VWAP + 20 bp (after 09:40)
#             VBD  first 5m close below VWAP - 20 bp (after 09:40)
#   MODE "C"  PDL / PDH  first RTH minute touching the prior day's low / high
#             ONL / ONH  first RTH minute touching the overnight low / high
#
# Entry is the close of the signalling bar; tracking starts on the next
# minute, so nothing inside the signal bar counts.
#
# Tag: G,<yyyymmdd>,<type>,<hhmm>,<entry>,<prior close>,<prior high>,
#      <prior low>,<open 09:30>,<ON high>,<ON low>,<vwap>,<OR high>,<OR low>,
#      <up x13>,<dn x13>,<eod pts>
#   up/dn = first minute (1 = the minute after entry) price is LEVELS[i] bp
#   above / below entry, -1 if never by 15:55

MODE = "B"
LEVELS = [5, 10, 15, 20, 25, 30, 40, 50, 60, 75, 100, 125, 150]
TIMES = {9 * 60 + 31: "T931", 10 * 60: "T1000", 10 * 60 + 30: "T1030", 11 * 60: "T1100"}
EOD = 15 * 60 + 55


class CondBracketExporter(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2018, 1, 1)
        self.SetEndDate(2025, 12, 31)
        self.SetCash(1_000_000)
        self.n_tags = 0
        self.fut = self.AddFuture(
            Futures.Indices.NASDAQ100EMini, Resolution.Minute,
            dataNormalizationMode=DataNormalizationMode.Raw,
            dataMappingMode=DataMappingMode.OpenInterest,
            contractDepthOffset=0, extendedMarketHours=True)
        self.fut.SetFilter(0, 180)
        self.day = None
        self.trk = []
        self.pc = self.pdh = self.pdl = None
        self.on_h = self.on_l = None
        self._reset_day()

    def _reset_day(self):
        self.o930 = None
        self.onh = self.onl = None
        self.rth_h = self.rth_l = None
        self.pv = self.vol = 0.0
        self.orh = self.orl = None
        self.b5 = None
        self.done = set()

    # ------------------------------------------------------------------
    def OnData(self, slice):
        if slice.Bars is None:
            return
        bar = slice.Bars.get(self.fut.Symbol)
        if bar is None:
            return
        t = self.Time
        hm = t.hour * 60 + t.minute          # bar end time, ET
        o, h, l, c = float(bar.Open), float(bar.High), float(bar.Low), float(bar.Close)
        v = float(bar.Volume)
        if self.day != t.date():
            for tr in self.trk:
                self._emit(tr, tr["last"])
            self.trk = []
            self.day = t.date()
            self._reset_day()

        self._track(h, l, c, hm)

        # overnight range: everything after the 16:00 close up to 09:30
        if hm > 16 * 60 or hm <= 9 * 60 + 30:
            if hm == 16 * 60 + 1 or self.on_h is None:
                self.on_h, self.on_l = h, l
            else:
                self.on_h, self.on_l = max(self.on_h, h), min(self.on_l, l)
            return
        if t.weekday() >= 5:
            return

        # regular session, bars ending 09:31 .. 16:00
        if hm == 9 * 60 + 31:
            self.o930 = o
            self.onh, self.onl = self.on_h, self.on_l
        if self.o930 is None:
            return
        self.rth_h = h if self.rth_h is None else max(self.rth_h, h)
        self.rth_l = l if self.rth_l is None else min(self.rth_l, l)
        self.pv += (h + l + c) / 3.0 * v
        self.vol += v
        vwap = self.pv / self.vol if self.vol > 0 else c
        if hm <= 9 * 60 + 45:
            self.orh = h if self.orh is None else max(self.orh, h)
            self.orl = l if self.orl is None else min(self.orl, l)

        if hm == 16 * 60:
            self.pc, self.pdh, self.pdl = c, self.rth_h, self.rth_l
            return
        if self.pc is None or hm > 15 * 60:
            return

        if MODE == "A" and hm in TIMES:
            self._open(TIMES[hm], hm, c, vwap)

        if MODE == "B":
            b = self.b5
            if b is None:
                self.b5 = b = [h, l, c]
            else:
                b[0], b[1], b[2] = max(b[0], h), min(b[1], l), c
            if hm % 5 == 0:
                self.b5 = None
                cl = b[2]
                if hm > 9 * 60 + 45:
                    if cl > self.orh and cl > vwap:
                        self._first("ORB", hm, cl, vwap)
                    if cl < self.orl and cl < vwap:
                        self._first("ORS", hm, cl, vwap)
                if hm >= 9 * 60 + 40:
                    if cl > vwap * 1.002:
                        self._first("VBU", hm, cl, vwap)
                    if cl < vwap * 0.998:
                        self._first("VBD", hm, cl, vwap)

        if MODE == "C":
            if l <= self.pdl:
                self._first("PDL", hm, c, vwap)
            if h >= self.pdh:
                self._first("PDH", hm, c, vwap)
            if self.onl is not None and l <= self.onl:
                self._first("ONL", hm, c, vwap)
            if self.onh is not None and h >= self.onh:
                self._first("ONH", hm, c, vwap)

    # ------------------------------------------------------------------
    def _first(self, typ, hm, px, vwap):
        if typ in self.done:
            return
        self.done.add(typ)
        self._open(typ, hm, px, vwap)

    def _open(self, typ, hm, px, vwap):
        self.trk.append({
            "ctx": (f"G,{self.Time.strftime('%Y%m%d')},{typ},{hm},{px:.2f},{self.pc:.2f},"
                    f"{self.pdh:.2f},{self.pdl:.2f},{self.o930:.2f},"
                    f"{(self.onh or 0):.2f},{(self.onl or 0):.2f},{vwap:.2f},"
                    f"{(self.orh or 0):.2f},{(self.orl or 0):.2f}"),
            "e": px, "k": 0, "up": [-1] * len(LEVELS), "dn": [-1] * len(LEVELS),
            "last": 0.0})

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
            if hm >= EOD and hm <= 16 * 60:
                self._emit(tr, tr["last"])
            else:
                keep.append(tr)
        self.trk = keep

    def _emit(self, tr, eod):
        tag = (tr["ctx"] + "," + ",".join(str(x) for x in tr["up"]) + ","
               + ",".join(str(x) for x in tr["dn"]) + f",{eod:.2f}")
        try:
            sym = self.fut.Mapped
            if sym is not None and sym in self.Securities:
                px = self.Securities[sym].Price
                if px > 0:
                    tkt = self.LimitOrder(sym, 1, round(px * 0.5, 0), tag=tag)
                    tkt.Cancel()
                    self.n_tags += 1
        except Exception as ex:
            self.Debug(f"tag fail: {ex}")

    def OnEndOfAlgorithm(self):
        self.Log(f"TAGS={self.n_tags}")
