# region imports
from AlgorithmImports import *
from collections import deque
# endregion
#
# LIVE-SPEC EXPORTER: re-implements the live TradingView indicators exactly as
# written (independently of the research exporters) on NQ 1-minute data and
# emits every trade, so the book is measured on the rules actually traded.
#
# MODE "VWAP" (Lucid 2/3, SL 25 / TP 100 pt, not Wednesday, one trade a day):
#   P5   indicator on a 5-minute chart: close crosses the RTH VWAP (5-min hlc3)
#   P1   indicator on a 1-minute chart: close crosses the RTH VWAP (1-min hlc3)
#   B5   research version: 5-minute close breaks VWAP +/- 0.20% (first only)
#   Entry at the signal bar's close while the bar opened before 15:50; stop and
#   target managed on 1-minute bars from the next minute (bar touching both =
#   stop; stop fills at the worse of stop and bar open, target at the target);
#   otherwise flat at the close of the bar opening at 15:55.
# MODE "ORB" (Lucid 1 on a 5-minute chart, see _orb): variant O5.
# MODE "NOISE" (Lucid 6 on a 1-minute chart): noise area from the last 14
#   sessions at 10:00..15:30 checks; long above max(open, prior close) x
#   (1 + sigma), short below the mirror; exit at a check when the close is
#   beyond max(band, VWAP) / min(band, VWAP) or on an opposite signal (which
#   reverses); flat at 15:55.
#   N0   published rules
#   NS   with the 0.50% hard stop; after a stop no entry until the stopped
#        trade's normal exit (as in the indicator)
#
# Tag: L,<variant>,<yyyymmdd>,<dir>,<entry hhmm>,<entry>,<exit hhmm>,<exit>,
#      <reason>,<rv20 x1000 known at the open>

MODE = "NOISE"
START, END = 2018, 2025
TICKER = Futures.Energies.CRUDE_OIL_WTI
SL_PTS, TP_PTS = 25.0, 100.0
BAND = 0.002
LOOKBACK = 14
HARD_STOP = 0.005
CHECKS = list(range(600, 931, 30))


class LiveSpecExporter(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(START, 1, 1)
        self.SetEndDate(END, 12, 31)
        self.SetCash(1_000_000)
        self.n_tags = 0
        self.fut = self.AddFuture(TICKER, Resolution.Minute,
                                  dataNormalizationMode=DataNormalizationMode.Raw,
                                  dataMappingMode=DataMappingMode.OpenInterest,
                                  contractDepthOffset=0, extendedMarketHours=False)
        self.fut.SetFilter(0, 180)
        self.closes = deque(maxlen=21)
        self.noise = {c: deque(maxlen=LOOKBACK) for c in CHECKS}
        self.prior_close = None
        self.day = None
        self.rv = 0

    # ---------- helpers ----------
    def _rv20(self):
        xs = list(self.closes)
        if len(xs) < 21:
            return 0
        r = [xs[i] / xs[i - 1] - 1.0 for i in range(1, len(xs))]
        m = sum(r) / len(r)
        return int(round((sum((x - m) ** 2 for x in r) / (len(r) - 1)) ** 0.5 * 252 ** 0.5 * 1000))

    def _new_day(self):
        self.rv = self._rv20()
        self.o = None
        self.pv1 = self.v1 = 0.0
        self.pv5 = self.v5 = 0.0
        self.b5 = None
        self.prev1 = None            # (close, vwap) of the previous 1-min bar
        self.prev5 = None            # (close, vwap, upper, lower) of the previous 5-min bar
        self.vw = {k: {"done": False, "tr": None} for k in ("P5", "P1", "B5")}
        self.nz = {k: {"pos": 0, "e": None, "ehm": None, "ghost": 0} for k in ("N0", "NS")}
        self.ob = {"b": None, "pv": 0.0, "v": 0.0, "ema": None, "orh": None, "orl": None, "set": False, "tr": None}

    def _emit(self, var, d, ehm, e, xhm, x, why):
        tag = f"L,{var},{self.day.strftime('%Y%m%d')},{d},{ehm},{e:.2f},{xhm},{x:.2f},{why},{self.rv}"
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

    # ---------- data ----------
    def OnData(self, slice):
        if slice.Bars is None:
            return
        bar = slice.Bars.get(self.fut.Symbol)
        if bar is None:
            return
        t = self.Time
        hm = t.hour * 60 + t.minute                      # bar END minute, ET
        if not (9 * 60 + 30 < hm <= 16 * 60) or t.weekday() >= 5:
            return
        if self.day != t.date():
            self.day = t.date()
            self._new_day()
        o, h, l, c, v = (float(bar.Open), float(bar.High), float(bar.Low),
                         float(bar.Close), float(bar.Volume))
        if hm == 9 * 60 + 31:
            self.o = o
        if self.o is None:
            return
        if MODE == "VWAP":
            self._vwap(hm, o, h, l, c, v)
        elif MODE == "ORB":
            self._orb(hm, o, h, l, c, v)
        else:
            self._noise(hm, o, h, l, c, v)
        if hm == 16 * 60:
            self.closes.append(c)
            self.prior_close = c

    # ---------- Lucid 2: VWAP ----------
    def _manage(self, k, hm, o, h, l, c):
        s = self.vw[k]
        tr = s["tr"]
        if tr is None or hm <= tr["ehm"]:
            return
        d, e = tr["d"], tr["e"]
        sl, tp = e - d * SL_PTS, e + d * TP_PTS
        x = why = None
        if (d == 1 and l <= sl) or (d == -1 and h >= sl):
            x, why = (min(sl, o) if d == 1 else max(sl, o)), "SL"
        elif (d == 1 and h >= tp) or (d == -1 and l <= tp):
            x, why = tp, "TP"
        elif hm == tr["eod"]:
            x, why = c, "EOD"
        if x is not None:
            self._emit(k, d, tr["ehm"], e, hm, x, why)
            s["tr"] = None
            s["done"] = True

    def _enter(self, k, d, hm, c, eod):
        s = self.vw[k]
        if s["tr"] is None and not s["done"]:
            s["tr"] = {"d": d, "e": c, "ehm": hm, "eod": eod}

    def _vwap(self, hm, o, h, l, c, v):
        wed = self.day.weekday() == 2
        for k in ("P5", "P1", "B5"):
            self._manage(k, hm, o, h, l, c)
        # 1-minute chart version
        self.pv1 += (h + l + c) / 3.0 * v
        self.v1 += v
        vw1 = self.pv1 / self.v1 if self.v1 > 0 else c
        if self.prev1 is not None and not wed and hm - 1 < 15 * 60 + 50:
            pc, pvw = self.prev1
            if c > vw1 and pc <= pvw:
                self._enter("P1", 1, hm, c, 15 * 60 + 56)
            elif c < vw1 and pc >= pvw:
                self._enter("P1", -1, hm, c, 15 * 60 + 56)
        self.prev1 = (c, vw1)
        # 5-minute bars (end at hm % 5 == 0)
        b = self.b5
        if b is None:
            b = self.b5 = [o, h, l, c, v]
        else:
            b[1] = max(b[1], h)
            b[2] = min(b[2], l)
            b[3] = c
            b[4] += v
        if hm % 5 == 0:
            self.b5 = None
            bo, bh, bl, bc, bv = b
            self.pv5 += (bh + bl + bc) / 3.0 * max(bv, 1.0)
            self.v5 += max(bv, 1.0)
            vw5 = self.pv5 / self.v5
            up, lo = vw5 * (1 + BAND), vw5 * (1 - BAND)
            if self.prev5 is not None and not wed and hm - 5 < 15 * 60 + 50:
                pc, pvw, pup, plo = self.prev5
                if bc > vw5 and pc <= pvw:
                    self._enter("P5", 1, hm, bc, 16 * 60)
                elif bc < vw5 and pc >= pvw:
                    self._enter("P5", -1, hm, bc, 16 * 60)
                if bc > up and pc <= pup:
                    self._enter("B5", 1, hm, bc, 16 * 60)
                elif bc < lo and pc >= plo:
                    self._enter("B5", -1, hm, bc, 16 * 60)
            self.prev5 = (bc, vw5, up, lo)

    # ---------- Lucid 1: ORB 15 min long, 5-minute chart ----------
    # 5-minute bars from 1-minute bars (bar start = end - 5). OR = bars starting
    # 09:30-09:40; entry when a bar starting after 09:45 and before 15:00 closes
    # above the OR high and the RTH VWAP (5-min hlc3), not Wednesday, no open
    # position; stop max(OR low, close - OR range); from the next bar: stop hit
    # (low <= stop) fills at min(stop, bar open), else flat at the close of the
    # bar starting 15:55, else the stop rises to the RTH 20-EMA of 5-min closes
    # (restarted each session). Re-enters after every exit.
    def _orb(self, hm, o, h, l, c, v):
        s = self.ob
        b = s["b"]
        if b is None:
            b = s["b"] = [o, h, l, c, v]
        else:
            b[1] = max(b[1], h)
            b[2] = min(b[2], l)
            b[3] = c
            b[4] += v
        if hm % 5 != 0:
            return
        s["b"] = None
        bo, bh, bl, bc, bv = b
        st_ = hm - 5                                   # bar start minute
        s["pv"] += (bh + bl + bc) / 3.0 * bv
        s["v"] += bv
        vw = s["pv"] / s["v"] if s["v"] > 0 else bc
        k = 2.0 / 21.0
        s["ema"] = bc if s["ema"] is None else bc * k + s["ema"] * (1 - k)
        if 9 * 60 + 30 <= st_ < 9 * 60 + 45:
            s["orh"] = bh if s["orh"] is None else max(s["orh"], bh)
            s["orl"] = bl if s["orl"] is None else min(s["orl"], bl)
        if st_ >= 9 * 60 + 45 and s["orh"] is not None:
            s["set"] = True
        trig = (s["set"] and self.day.weekday() != 2 and 9 * 60 + 45 < st_ < 15 * 60
                and bc > s["orh"] and bc > vw and s["tr"] is None)
        tr = s["tr"]
        if tr is not None and hm > tr["ehm"]:
            x = why = None
            if bl <= tr["sl"]:
                x, why = min(tr["sl"], bo), "SL"
            elif st_ >= 15 * 60 + 55:
                x, why = bc, "EOD"
            elif s["ema"] > tr["sl"]:
                tr["sl"] = s["ema"]
            if x is not None:
                self._emit("O5", 1, tr["ehm"], tr["e"], hm, x, why)
                s["tr"] = None
        if trig:
            rng = s["orh"] - s["orl"]
            sl0 = max(s["orl"], bc - rng)
            if sl0 < bc:
                s["tr"] = {"e": bc, "sl": sl0, "ehm": hm}

    # ---------- Lucid 6: noise momentum ----------
    def _noise(self, hm, o, h, l, c, v):
        self.pv1 += (h + l + c) / 3.0 * v
        self.v1 += v
        vw = self.pv1 / self.v1 if self.v1 > 0 else c
        s = self.nz["NS"]
        if s["pos"] != 0 and hm > s["ehm"]:
            stop = s["e"] * (1 - s["pos"] * HARD_STOP)
            if (s["pos"] == 1 and l <= stop) or (s["pos"] == -1 and h >= stop):
                x = min(stop, o) if s["pos"] == 1 else max(stop, o)
                self._emit("NS", s["pos"], s["ehm"], s["e"], hm, x, "STOP")
                s["ghost"], s["pos"], s["e"] = s["pos"], 0, None
        if hm in CHECKS:
            buf = self.noise[hm]
            ready = len(buf) == LOOKBACK and self.prior_close is not None
            sigma = sum(buf) / LOOKBACK if ready else 0.0
            buf.append(abs(c / self.o - 1.0))
            if ready:
                ub = max(self.o, self.prior_close) * (1 + sigma)
                lb = min(self.o, self.prior_close) * (1 - sigma)
                sig = 1 if c > ub else (-1 if c < lb else 0)
                for k, s in self.nz.items():
                    if s["pos"] != 0 or s["ghost"] != 0:
                        d = s["pos"] if s["pos"] != 0 else s["ghost"]
                        out = c < max(ub, vw) if d == 1 else c > min(lb, vw)
                        if out or (sig != 0 and sig != d):
                            if s["pos"] != 0:
                                self._emit(k, s["pos"], s["ehm"], s["e"], hm, c, "EXIT")
                            s["pos"], s["e"], s["ghost"] = 0, None, 0
                    if s["pos"] == 0 and s["ghost"] == 0 and sig != 0:
                        s["pos"], s["e"], s["ehm"] = sig, c, hm
        if hm == 15 * 60 + 55:
            for k, s in self.nz.items():
                if s["pos"] != 0:
                    self._emit(k, s["pos"], s["ehm"], s["e"], hm, c, "EOD")
                s["pos"], s["e"], s["ghost"] = 0, None, 0

    def OnEndOfAlgorithm(self):
        self.Log(f"TAGS={self.n_tags} MODE={MODE}")
