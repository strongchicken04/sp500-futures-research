# region imports
from AlgorithmImports import *
# endregion
#
# OVERNIGHT SESSION EXPORTER (Globex 18:00-09:29 ET), same tag layout as the
# conditional bracket exporter so the same scorers read it.
#
#   LBU / LBD  first 5m close above / below the Asian range (18:00-02:00)
#              between 02:00 and 08:00 (London breakout)
#   LTH / LTL  first minute touching the Asian high / low after 02:00
#   T300       03:00 ET (London open), unconditional
#   T800       08:00 ET, unconditional
# Context fields: prior RTH close/high/low, the 18:00 Globex open in place of
# the 09:30 open, the Asian high/low in place of the overnight high/low, and
# the Globex VWAP. Tracking runs from the minute after entry to 09:29 ET.

INST = "NQ"
TICKERS = {"NQ": Futures.Indices.NASDAQ_100_E_MINI, "ES": Futures.Indices.SP_500_E_MINI}
LEVELS = [5, 10, 15, 20, 25, 30, 40, 50, 60, 75, 100, 125, 150]
END = 9 * 60 + 29


class OvernightExporter(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2018, 1, 1)
        self.SetEndDate(2025, 12, 31)
        self.SetCash(1_000_000)
        self.n_tags = 0
        self.fut = self.AddFuture(
            TICKERS[INST], Resolution.Minute,
            dataNormalizationMode=DataNormalizationMode.Raw,
            dataMappingMode=DataMappingMode.OpenInterest,
            contractDepthOffset=0, extendedMarketHours=True)
        self.fut.SetFilter(0, 180)
        self.trk = []
        self.pc = self.pdh = self.pdl = None
        self.rth_h = self.rth_l = None
        self.live = False
        self._reset()

    def _reset(self):
        self.g_open = None
        self.ah = self.al = None
        self.pv = self.vol = 0.0
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
        self._track(h, l, c, hm)

        # regular session bookkeeping for the prior-day context
        if 9 * 60 + 30 < hm <= 16 * 60:
            self.rth_h = h if self.rth_h is None or hm == 9 * 60 + 31 else max(self.rth_h, h)
            self.rth_l = l if self.rth_l is None or hm == 9 * 60 + 31 else min(self.rth_l, l)
            if hm == 16 * 60:
                self.pc, self.pdh, self.pdl = c, self.rth_h, self.rth_l
            return

        # a Globex session starts with the first bar after 18:00
        if 18 * 60 < hm <= 18 * 60 + 5 and not self.live:
            for tr in self.trk:
                self._emit(tr)
            self.trk = []
            self._reset()
            self.live = True
            self.g_open = o
        if not self.live or self.pc is None or self.g_open is None:
            return
        if 9 * 60 + 30 >= hm > END:
            self.live = False
            return

        self.pv += (h + l + c) / 3.0 * v
        self.vol += v
        vwap = self.pv / self.vol if self.vol > 0 else c
        asia = hm > 18 * 60 or hm <= 2 * 60
        if asia:
            self.ah = h if self.ah is None else max(self.ah, h)
            self.al = l if self.al is None else min(self.al, l)
            return
        if self.ah is None or hm > 8 * 60 + 30:
            return

        b = self.b5
        if b is None:
            self.b5 = b = [h, l, c]
        else:
            b[0], b[1], b[2] = max(b[0], h), min(b[1], l), c
        if hm % 5 == 0:
            self.b5 = None
            if hm <= 8 * 60:
                if b[2] > self.ah:
                    self._first("LBU", hm, b[2], vwap)
                if b[2] < self.al:
                    self._first("LBD", hm, b[2], vwap)
        if h >= self.ah:
            self._first("LTH", hm, c, vwap)
        if l <= self.al:
            self._first("LTL", hm, c, vwap)
        if hm == 3 * 60:
            self._first("T300", hm, c, vwap)
        if hm == 8 * 60:
            self._first("T800", hm, c, vwap)

    def _first(self, typ, hm, px, vwap):
        if typ in self.done:
            return
        self.done.add(typ)
        d = self.Time.strftime('%Y%m%d')
        self.trk.append({
            "ctx": (f"G,{d},{typ},{hm},{px:.2f},{self.pc:.2f},{self.pdh:.2f},{self.pdl:.2f},"
                    f"{self.g_open:.2f},{self.ah:.2f},{self.al:.2f},{vwap:.2f},0,0"),
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
            if hm == END:
                self._emit(tr)
            else:
                keep.append(tr)
        self.trk = keep

    def _emit(self, tr):
        tag = (tr["ctx"] + "," + ",".join(str(x) for x in tr["up"]) + ","
               + ",".join(str(x) for x in tr["dn"]) + f",{tr['last']:.2f}")
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
