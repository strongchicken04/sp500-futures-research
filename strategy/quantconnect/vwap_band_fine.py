# region imports
from AlgorithmImports import *
# endregion
#
# VWAP BAND EXPORTER: the VWAP band at several distances, every bracket.
#
# For each band distance D in DISTS (basis points from the session VWAP),
# the first 5-minute close above VWAP + D (type U<D>) and the first below
# VWAP - D (type D<D>) after 09:40 are entries. Entry is the close of that
# 5-minute bar; from the next minute the first touch of every LEVELS bp move
# up and down is recorded to 15:55, so direction, target and stop can be set
# offline (targets and stops are later expressed as a share of ATR).
#
# Tag: same layout as cond_bracket_exporter (G,...), with the finer LEVELS.

DISTS = [20, 40, 60]
LEVELS = [1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30, 40, 50, 60]

EOD = 15 * 60 + 55


class VwapBandExporter(QCAlgorithm):

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
        self.vah = self.val = None
        self.noise = {}
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
        self.ibh = self.ibl = None
        self.prof = {}
        self.va_open = 0

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

        if hm <= 10 * 60 + 30:
            self.ibh = h if self.ibh is None else max(self.ibh, h)
            self.ibl = l if self.ibl is None else min(self.ibl, l)
        key = round((h + l + c) / 3.0)
        self.prof[key] = self.prof.get(key, 0.0) + v
        # noise area: absolute move from the open at this minute of the day
        mv = abs(c / self.o930 - 1.0)
        hist = self.noise.setdefault(hm, [])
        sigma = sum(hist) / len(hist) if len(hist) >= 14 else None
        hist.append(mv)
        if len(hist) > 14:
            hist.pop(0)

        if hm == 16 * 60:
            self.pc, self.pdh, self.pdl = c, self.rth_h, self.rth_l
            self._value_area()
            return
        if self.pc is None or hm > 15 * 60:
            return

        b = self.b5
        if b is None:
            self.b5 = b = [h, l, c]
        else:
            b[0], b[1], b[2] = max(b[0], h), min(b[1], l), c
        bar5 = hm % 5 == 0
        if bar5:
            self.b5 = None
        cl = b[2]

        if bar5 and hm >= 9 * 60 + 40:
            for d in DISTS:
                if cl > vwap * (1.0 + d / 1e4):
                    self._first(f"U{d}", hm, cl, vwap)
                if cl < vwap * (1.0 - d / 1e4):
                    self._first(f"D{d}", hm, cl, vwap)

    def _value_area(self):
        """70% of the session's volume around its point of control."""
        if not self.prof:
            return
        px = sorted(self.prof)
        tot = sum(self.prof.values())
        poc = max(px, key=lambda k: self.prof[k])
        i = j = px.index(poc)
        acc = self.prof[poc]
        while acc < 0.7 * tot and (i > 0 or j < len(px) - 1):
            lo = self.prof[px[i - 1]] if i > 0 else -1
            hi = self.prof[px[j + 1]] if j < len(px) - 1 else -1
            if hi >= lo:
                j += 1
                acc += hi
            else:
                i -= 1
                acc += lo
        self.val, self.vah = px[i], px[j]

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
