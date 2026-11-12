# region imports
from AlgorithmImports import *
import math
from collections import deque
# endregion
#
# TWO OWNER STRATEGIES (2026-11-12), NQ minute bars 2010-2026, INSIDE QuantConnect,
# aggregates only. Central Time = ET - 1 h. Rules as given; unclear points as
# variants; FIXED BEFORE RESULTS.
#
# S2 "VWAP PULLBACK + ADX" (1-min, long only). Opening range 08:30-09:00 CT.
#   1) a 1-min candle closes above the OR high -> setup active; 2) price touches
#   the VWAP (low <= VWAP); 3) a candle closes back above the VWAP (2 and 3 may be
#   the same candle); 4) ADX > 20 and not rising (ADX <= previous). Entry at the
#   next candle's open; while ADX rises, wait until it stops (a close back below
#   the VWAP resets steps 2-3). TP = highest high of the last 5 candles (limit),
#   SL = lowest low of the last 20 candles (stop); skip if TP <= entry. Time exit
#   15:55 CT (literal; that is after the RTH close) or 14:55 CT (likely meant).
#   Variants: ADX period 14 / 7; VWAP from the RTH open (08:30 CT) / from midnight
#   CT; max trades a day 1 / 3 (a new trade needs steps 2-4 again).
# S3 "OVERNIGHT BIAS ORB" (15-min, long and short). Overnight range 23:00 CT
#   (variant 00:00 CT) .. 08:30 CT. Bias: the 08:30 CT open in the top third of the
#   overnight range (or above it) -> long only; bottom third (or below) -> short
#   only; middle -> no trade. OR = the 08:30-08:45 CT candle. A 15-min candle that
#   CLOSES beyond the OR high (long) / low (short) with ADX(14, 15-min) > 20 ->
#   entry at the next candle's open; one trade a day; the opposite break does not
#   cancel. SL = 0.30 x the 15-day mean of the daily range (ATR basis: full CT
#   session 00:00-16:00 CT, variant RTH 08:30-15:00 CT); TP = 3 x SL; time exit
#   14:30 CT. Controls: NOBIAS (first break either side, with ADX), NOADX.
# Fills: stop first if both in one minute; gaps fill at the open; limit TP at the
#   level or a better open. Costs $15 per NQ round trip. Results per trade in
#   points (gross / net) and R (net P&L / initial risk); $ a year per NQ at today's
#   price (points scaled by 28,530 / entry); eras 2010-13 / 14-17 / 18-21 / 22-26.

START = (2010, 1, 1)
END = (2026, 12, 31)
PRICE, PV, COST = 28530.0, 20.0, 15.0
ERAS = ((2010, 2013), (2014, 2017), (2018, 2021), (2022, 2026))


def era_of(y):
    for i, (a, b) in enumerate(ERAS):
        if a <= y <= b:
            return i
    return None


class ADX:
    def __init__(self, n):
        self.n = n
        self.ph = self.pl = self.pc = None
        self.tr = self.pdm = self.ndm = None
        self.adx = None
        self.prev = None
        self.k = 0

    def update(self, h, l, c):
        if self.pc is None:
            self.ph, self.pl, self.pc = h, l, c
            return
        tr = max(h - l, abs(h - self.pc), abs(l - self.pc))
        up, dn = h - self.ph, self.pl - l
        pdm = up if (up > dn and up > 0) else 0.0
        ndm = dn if (dn > up and dn > 0) else 0.0
        n = self.n
        if self.tr is None:
            self.tr, self.pdm, self.ndm = tr, pdm, ndm
        else:
            self.tr += (tr - self.tr) / n
            self.pdm += (pdm - self.pdm) / n
            self.ndm += (ndm - self.ndm) / n
        if self.tr > 0:
            pdi, ndi = 100 * self.pdm / self.tr, 100 * self.ndm / self.tr
            dx = 100 * abs(pdi - ndi) / (pdi + ndi) if pdi + ndi > 0 else 0.0
            self.prev = self.adx
            self.adx = dx if self.adx is None else self.adx + (dx - self.adx) / n
            self.k += 1
        self.ph, self.pl, self.pc = h, l, c

    def ready(self):
        return self.k > 3 * self.n and self.prev is not None


class S2:
    def __init__(self, key):
        self.key = key            # (adxn, vwap, maxt, tex)
        self.trades = []
        self.reset_day()

    def reset_day(self):
        self.active = False
        self.touched = False
        self.ready = False
        self.pending = None       # entry at next minute open
        self.pos = None
        self.n = 0


class S3:
    def __init__(self, key):
        self.key = key            # (on_start, atr_basis, mode)
        self.trades = []
        self.reset_day()

    def reset_day(self):
        self.pending = None
        self.pos = None
        self.done = False


class TwoStrategiesInQC(QCAlgorithm):

    def initialize(self):
        self.set_start_date(*START)
        self.set_end_date(*END)
        self.set_cash(1_000_000)
        self.f = self.add_future(Futures.Indices.NASDAQ_100_E_MINI, Resolution.MINUTE, fill_forward=False,
                                 data_normalization_mode=DataNormalizationMode.RAW,
                                 data_mapping_mode=DataMappingMode.OPEN_INTEREST,
                                 contract_depth_offset=0, extended_market_hours=True)
        self.f.set_filter(0, 180)
        self.adx1 = {14: ADX(14), 7: ADX(7)}
        self.adx15 = ADX(14)
        self.b15 = None
        self.hist_h = deque(maxlen=20)
        self.hist_l = deque(maxlen=20)
        self.s2 = [S2((a, v, mt, tx)) for a in (14, 7) for v in ("RTH", "MID") for mt in (1, 3) for tx in ("1555CT", "1455CT")]
        self.s3 = [S3((o, b, md)) for o in ("23CT", "00CT") for b in ("FULL", "RTH") for md in ("MAIN",)]
        self.s3 += [S3(("23CT", "FULL", "NOBIAS")), S3(("23CT", "FULL", "NOADX"))]
        self.date = None
        self.mapped = None
        self.full_rng = deque(maxlen=15)
        self.rth_rng = deque(maxlen=15)
        self._new_day_state()

    def _new_day_state(self):
        self.on = {"23CT": [None, None], "00CT": [None, None]}
        self.vw = {"RTH": [0.0, 0.0], "MID": [0.0, 0.0]}
        self.orh30 = None
        self.or15 = None
        self.ropen = None
        self.fhi = self.flo = None       # full CT session range (01:00-17:00 ET)
        self.rhi = self.rlo = None       # RTH range

    def _book(self, s, px, t):
        p = s.pos
        pts = (px - p["e"]) * p["d"]
        net = pts - COST / PV
        s.trades.append((pts, net / p["risk"], net * PRICE / p["e"] * PV, era_of(t.year), t.year))
        s.pos = None

    def _manage(self, s, o, h, l, c, m, tex):
        p = s.pos
        if p is None:
            return
        if p["d"] == 1:
            if l <= p["sl"]:
                self._book(s, min(p["sl"], o), self.time)
            elif h >= p["tp"]:
                self._book(s, max(p["tp"], o), self.time)
        else:
            if h >= p["sl"]:
                self._book(s, max(p["sl"], o), self.time)
            elif l <= p["tp"]:
                self._book(s, min(p["tp"], o), self.time)
        if s.pos is not None and m >= tex:
            self._book(s, c, self.time)

    def on_data(self, data: Slice):
        bar = data.bars.get(self.f.symbol)
        if bar is None:
            return
        t = self.time
        m = t.hour * 60 + t.minute                  # ET, bar end
        o, h, l, c, v = float(bar.open), float(bar.high), float(bar.low), float(bar.close), float(bar.volume)
        # indicators that run all session
        for a in self.adx1.values():
            a.update(h, l, c)
        b = self.b15
        self.b15 = [o, h, l, c] if b is None else [b[0], max(b[1], h), min(b[2], l), c]
        close15 = (m % 15 == 0)
        if close15:
            bb = self.b15
            self.adx15.update(bb[1], bb[2], bb[3])
            self.b15 = None
        # new trading day: first bar after 00:00 ET (23:00 CT) with a new date
        if 0 < m <= 17 * 60 and self.date != t.date():
            if self.date is not None:
                if self.fhi is not None:
                    self.full_rng.append(self.fhi - self.flo)
                if self.rhi is not None:
                    self.rth_rng.append(self.rhi - self.rlo)
            self.date = t.date()
            self.mapped = self.f.mapped
            self._new_day_state()
            for s in self.s2 + self.s3:
                if s.pos is not None:
                    self._book(s, c, t)
                s.reset_day()
        if self.date != t.date() or not (0 < m <= 17 * 60):
            return
        if self.f.mapped != self.mapped:             # roll: flat, no more trades today
            for s in self.s2 + self.s3:
                if s.pos is not None:
                    self._book(s, c, t)
                s.pending = None
                if isinstance(s, S2):
                    s.n = 99
                else:
                    s.done = True
            self.mapped = self.f.mapped
        # ranges / VWAPs
        if 60 < m <= 17 * 60:
            self.fhi = h if self.fhi is None else max(self.fhi, h)
            self.flo = l if self.flo is None else min(self.flo, l)
            vw = self.vw["MID"]
            vw[0] += (h + l + c) / 3 * v
            vw[1] += v
        if m <= 9 * 60 + 30:
            for k, start in (("23CT", 0), ("00CT", 60)):
                if m > start:
                    r = self.on[k]
                    r[0] = h if r[0] is None else max(r[0], h)
                    r[1] = l if r[1] is None else min(r[1], l)
        rth = 9 * 60 + 30 < m <= 16 * 60
        if rth:
            if self.ropen is None:
                self.ropen = o
            self.rhi = h if self.rhi is None else max(self.rhi, h)
            self.rlo = l if self.rlo is None else min(self.rlo, l)
            vw = self.vw["RTH"]
            vw[0] += (h + l + c) / 3 * v
            vw[1] += v
            if m <= 10 * 60:
                self.orh30 = h if self.orh30 is None else max(self.orh30, h)
            if m <= 9 * 60 + 45:
                self.or15 = [h, l] if self.or15 is None else [max(self.or15[0], h), min(self.or15[1], l)]
        self.hist_h.append(h)
        self.hist_l.append(l)
        self._s2(o, h, l, c, m)
        self._s3(o, h, l, c, m, close15)

    # ------------------------------------------------------------------ S2
    def _s2(self, o, h, l, c, m):
        for s in self.s2:
            adxn, vwk, maxt, tx = s.key
            tex = 16 * 60 + 55 if tx == "1555CT" else 15 * 60 + 55
            # fill a pending entry at this minute's open
            if s.pending is not None and s.pos is None:
                pdn = s.pending
                s.pending = None
                e = o
                if pdn["tp"] > e and pdn["sl"] < e and m < tex:
                    s.pos = {"d": 1, "e": e, "tp": pdn["tp"], "sl": pdn["sl"], "risk": e - pdn["sl"]}
                    s.n += 1
            self._manage(s, o, h, l, c, m, tex)
            if not (10 * 60 < m < tex - 5) or self.orh30 is None or s.pos is not None or s.pending is not None or s.n >= maxt:
                continue
            vw = self.vw[vwk]
            if vw[1] <= 0:
                continue
            vwap = vw[0] / vw[1]
            if not s.active:
                if c > self.orh30:
                    s.active = True
                continue
            if l <= vwap:
                s.touched = True
            if c < vwap:
                s.ready = False
                continue
            if s.touched and c > vwap:
                s.ready = True
            a = self.adx1[adxn]
            if s.ready and a.ready() and a.adx > 20 and a.adx <= a.prev:
                tp = max(list(self.hist_h)[-5:])
                sl = min(self.hist_l)
                s.pending = {"tp": tp, "sl": sl}
                s.touched = False
                s.ready = False

    # ------------------------------------------------------------------ S3
    def _s3(self, o, h, l, c, m, close15):
        tex = 15 * 60 + 30
        for s in self.s3:
            on_k, basis, mode = s.key
            if s.pending is not None and s.pos is None:
                pdn = s.pending
                s.pending = None
                e = o
                d = pdn["d"]
                s.pos = {"d": d, "e": e, "sl": e - d * pdn["sld"], "tp": e + d * 3 * pdn["sld"], "risk": pdn["sld"]}
            self._manage(s, o, h, l, c, m, tex)
            if s.done or s.pos is not None or not close15 or not (9 * 60 + 45 < m <= 15 * 60 + 15):
                continue
            onr = self.on[on_k]
            rng = self.full_rng if basis == "FULL" else self.rth_rng
            if self.or15 is None or self.ropen is None or onr[0] is None or len(rng) < 15:
                continue
            hi, lo = onr
            pos_ = (self.ropen - lo) / (hi - lo) if hi > lo else 0.5
            bias = 1 if pos_ >= 2 / 3 else (-1 if pos_ <= 1 / 3 else 0)
            adx_ok = self.adx15.ready() and self.adx15.adx > 20
            d = 0
            if mode == "NOBIAS":
                if adx_ok:
                    d = 1 if c > self.or15[0] else (-1 if c < self.or15[1] else 0)
            else:
                if mode == "NOADX" or adx_ok:
                    if bias == 1 and c > self.or15[0]:
                        d = 1
                    elif bias == -1 and c < self.or15[1]:
                        d = -1
            if d != 0:
                sld = 0.30 * sum(rng) / 15.0
                s.pending = {"d": d, "sld": sld}
                s.done = True

    def on_end_of_algorithm(self):
        def summary(tr):
            n = len(tr)
            yrs = max(1.0, len(set(x[4] for x in tr)))
            pts = [x[0] for x in tr]
            rr = [x[1] for x in tr]
            usd = [x[2] for x in tr]
            mu = sum(usd) / n
            sd = math.sqrt(sum((x - mu) ** 2 for x in usd) / (n - 1)) if n > 1 else 0
            cum = pk = mdd = 0.0
            for x in usd:
                cum += x
                pk = max(pk, cum)
                mdd = min(mdd, cum - pk)
            era = " ".join(f"{sum(x[2] for x in tr if x[3] == i) / max(1, sum(1 for x in tr if x[3] == i)):+.0f}" for i in range(len(ERAS)))
            return (f"{n / yrs:.0f}/y win {sum(1 for x in pts if x > 0) / n * 100:.0f}% {sum(pts) / n:+.1f}pt {sum(rr) / n:+.3f}R "
                    f"${mu:+.0f}/tr t{(mu / (sd / math.sqrt(n)) if sd > 0 else 0):+.1f} ${sum(usd) / yrs:+,.0f}/y DD ${mdd:,.0f} | {era}")
        for s in self.s2:
            if len(s.trades) >= 10:
                a, vw, mt, tx = s.key
                self.set_runtime_statistic(f"S2 ADX{a} VW{vw} max{mt} {tx}", summary(s.trades))
        for s in self.s3:
            if len(s.trades) >= 10:
                o, bsis, md = s.key
                self.set_runtime_statistic(f"S3 ON{o} ATR{bsis} {md}", summary(s.trades))
