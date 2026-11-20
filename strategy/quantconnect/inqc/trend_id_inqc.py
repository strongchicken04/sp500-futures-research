# region imports
from AlgorithmImports import *
import math
from collections import deque
# endregion
#
# TREND-DAY IDENTIFICATION RELIABILITY (owner 2026-11-20: "not a trade signal - how reliably can we identify a
# trend; we design the signal ourselves"). NQ minute 2010-2026 INSIDE QuantConnect, aggregates only. FIXED
# BEFORE RESULTS:
# Truth (ex post, RTH 09:30-16:00 ET): ATR20 = mean RTH range of the previous 20 days.
#   T1 trend day: |C - O| >= 0.6 x (H - L); direction = sign(C - O).
#   T2 strong trend day: T1 and |C - O| >= 0.75 x ATR20.
# Detectors at tau = 10:00 / 10:30 / 11:00 ET from data up to tau only (p = close of the tau minute):
#   NA     Noise Area (Zarattini-Aziz-Barbon): sigma(tau) = mean |p/O - 1| at tau over the last 14 days;
#          up = max(O, prevC) x (1 + sigma), dn = min(O, prevC) x (1 - sigma); p > up -> +1, p < dn -> -1
#   NA15   the same with 1.5 x sigma
#   ADX    ADX(14) on 5-min candles (all hours) >= 25, direction = sign(+DI - -DI)
#   ER     efficiency ratio |p - O| / sum |1-min close changes| since the open >= its 80th percentile at tau
#          over the last 60 days, direction = sign(p - O)
#   ORV    p beyond the 09:30-10:00 range and on the same side of the RTH VWAP (not defined at 10:00)
#   GAP    sign(O - prevC) = sign(p - O) and |O - prevC| >= 0.25 x ATR20
#   EXT    range so far >= 0.6 x ATR20 and p in the top / bottom quarter of the day's range
#   VWP    p on one side of the RTH VWAP and >= 80% of RTH minute closes so far on that side
#   NA+ADX, NA+VWP  both agree
# Metrics per detector and tau: detection rate; precision = P(T1 / T2 day IN the detected direction |
#   detected) vs the base rates; recall = share of T2 days detected in the right direction; rest of day =
#   (C - p) x dir / ATR20: mean, share >= +0.25 ATR (continuation) and <= -0.25 ATR (reversal); T2
#   precision by era 2010-13 / 14-17 / 18-21 / 22-26. Days with a contract roll inside RTH are skipped.

START = (2010, 1, 1)
END = (2026, 12, 31)
TAUS = (10 * 60, 10 * 60 + 30, 11 * 60)
DETS = ("NA", "NA15", "ADX", "ER", "ORV", "GAP", "EXT", "VWP", "NA+ADX", "NA+VWP")
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
        return self.k > 3 * self.n



class TrendID(QCAlgorithm):

    def initialize(self):
        self.set_start_date(*START)
        self.set_end_date(*END)
        self.set_cash(1_000_000)
        self.f = self.add_future(Futures.Indices.NASDAQ_100_E_MINI, Resolution.MINUTE, fill_forward=False,
                                 data_normalization_mode=DataNormalizationMode.RAW,
                                 data_mapping_mode=DataMappingMode.OPEN_INTEREST,
                                 contract_depth_offset=0, extended_market_hours=True)
        self.f.set_filter(0, 180)
        self.adx5 = ADX(14)
        self.b5 = None
        self.mapped = None
        self.day = None
        self.prevC = None
        self.rngs = deque(maxlen=20)
        self.sig_hist = {t: deque(maxlen=14) for t in TAUS}
        self.er_hist = {t: deque(maxlen=60) for t in TAUS}
        # results: per (det, tau): counts
        self.res = {(d, t): {"n": 0, "t1": 0, "t2": 0, "rest": 0.0, "cont": 0, "rev": 0, "e2": [[0, 0] for _ in ERAS]}
                    for d in DETS for t in TAUS}
        self.rec = {(d, t): 0 for d in DETS for t in TAUS}
        self.base = {"days": 0, "t1": 0, "t2": 0, "e2": [[0, 0] for _ in ERAS]}
        self._new()

    def _new(self):
        self.O = self.H = self.L = self.C = None
        self.pv = self.vv = 0.0
        self.path = 0.0
        self.lastc = None
        self.above = self.below = self.nmin = 0
        self.orh = self.orl = None
        self.snap = {}
        self.bad = False

    def _close_day(self):
        if self.day is None or self.O is None or self.bad or len(self.rngs) < 20 or self.prevC is None:
            return
        atr = sum(self.rngs) / 20.0
        O, H, L, C = self.O, self.H, self.L, self.C
        body = C - O
        ddir = 1 if body > 0 else -1
        t1 = H > L and abs(body) >= 0.6 * (H - L)
        t2 = t1 and abs(body) >= 0.75 * atr
        e = era_of(self.day.year)
        self.base["days"] += 1
        self.base["t1"] += t1
        self.base["t2"] += t2
        if e is not None:
            self.base["e2"][e][1] += 1
            self.base["e2"][e][0] += t2
        for t, (p, dets) in self.snap.items():
            for d, dr in dets.items():
                if dr == 0:
                    continue
                r = self.res[(d, t)]
                r["n"] += 1
                ok1 = t1 and ddir == dr
                ok2 = t2 and ddir == dr
                r["t1"] += ok1
                r["t2"] += ok2
                mv = (C - p) * dr / atr
                r["rest"] += mv
                r["cont"] += mv >= 0.25
                r["rev"] += mv <= -0.25
                if e is not None:
                    r["e2"][e][1] += 1
                    r["e2"][e][0] += ok2
                if ok2:
                    self.rec[(d, t)] += 1

    def on_data(self, data: Slice):
        bar = data.bars.get(self.f.symbol)
        if bar is None:
            return
        t = self.time
        m = t.hour * 60 + t.minute
        o, h, l, c, v = float(bar.open), float(bar.high), float(bar.low), float(bar.close), float(bar.volume)
        b = self.b5
        self.b5 = [o, h, l, c] if b is None else [b[0], max(b[1], h), min(b[2], l), c]
        if m % 5 == 0:
            bb = self.b5
            self.adx5.update(bb[1], bb[2], bb[3])
            self.b5 = None
        rolled = self.mapped is not None and self.f.mapped != self.mapped
        self.mapped = self.f.mapped
        if not (9 * 60 + 30 < m <= 16 * 60):
            return
        if self.day != t.date():
            self._close_day()
            if self.day is not None and self.H is not None and not self.bad:
                self.rngs.append(self.H - self.L)
                self.prevC = self.C
            self.day = t.date()
            self._new()
        if rolled:
            self.bad = True
            self.prevC = None
        if self.O is None:
            self.O, self.H, self.L = o, h, l
        self.H, self.L, self.C = max(self.H, h), min(self.L, l), c
        self.pv += (h + l + c) / 3.0 * v
        self.vv += v
        vw = self.pv / self.vv if self.vv > 0 else c
        if self.lastc is not None:
            self.path += abs(c - self.lastc)
        self.lastc = c
        self.nmin += 1
        self.above += c > vw
        self.below += c < vw
        if m <= 10 * 60:
            self.orh = h if self.orh is None else max(self.orh, h)
            self.orl = l if self.orl is None else min(self.orl, l)
        if m not in TAUS or self.bad or self.prevC is None or len(self.rngs) < 20:
            return
        atr = sum(self.rngs) / 20.0
        O = self.O
        mv = abs(c / O - 1.0)
        dets = {}
        sh = self.sig_hist[m]
        if len(sh) == 14:
            sig = sum(sh) / 14.0
            for name, k in (("NA", 1.0), ("NA15", 1.5)):
                up = max(O, self.prevC) * (1 + k * sig)
                dn = min(O, self.prevC) * (1 - k * sig)
                dets[name] = 1 if c > up else (-1 if c < dn else 0)
        sh.append(mv)
        a = self.adx5
        if a.ready() and a.tr and a.tr > 0:
            dets["ADX"] = (1 if a.pdm > a.ndm else -1) if a.adx >= 25 else 0
        er = abs(c - O) / self.path if self.path > 0 else 0.0
        eh = self.er_hist[m]
        if len(eh) == 60:
            thr = sorted(eh)[int(0.8 * 60)]
            dets["ER"] = (1 if c > O else -1) if er >= thr else 0
        eh.append(er)
        if m > 10 * 60:
            dets["ORV"] = 1 if (c > self.orh and c > vw) else (-1 if (c < self.orl and c < vw) else 0)
        gap = O - self.prevC
        dets["GAP"] = (1 if gap > 0 else -1) if (abs(gap) >= 0.25 * atr and gap * (c - O) > 0) else 0
        rg = self.H - self.L
        if rg >= 0.6 * atr:
            dets["EXT"] = 1 if c >= self.H - 0.25 * rg else (-1 if c <= self.L + 0.25 * rg else 0)
        else:
            dets["EXT"] = 0
        dets["VWP"] = 1 if (c > vw and self.above >= 0.8 * self.nmin) else (-1 if (c < vw and self.below >= 0.8 * self.nmin) else 0)
        if "NA" in dets and "ADX" in dets:
            dets["NA+ADX"] = dets["NA"] if dets["NA"] != 0 and dets["NA"] == dets["ADX"] else 0
        if "NA" in dets:
            dets["NA+VWP"] = dets["NA"] if dets["NA"] != 0 and dets["NA"] == dets["VWP"] else 0
        self.snap[m] = (c, dets)

    def on_end_of_algorithm(self):
        self._close_day()
        B = self.base
        nd = B["days"]
        self.set_runtime_statistic("TID base", f"days {nd} | T1 {B['t1'] / nd * 100:.0f}% (one direction {B['t1'] / nd * 50:.0f}%) | T2 {B['t2'] / nd * 100:.0f}% (one direction {B['t2'] / nd * 50:.0f}%) | T2 by era "
                                   + "/".join(f"{x[0] / max(1, x[1]) * 100:.0f}" for x in B["e2"]))
        for d in DETS:
            for t in TAUS:
                r = self.res[(d, t)]
                n = r["n"]
                if n < 30:
                    continue
                lab = f"{t // 60}:{t % 60:02d}"
                self.set_runtime_statistic(f"TID {d} {lab}",
                    f"det {n / nd * 100:.0f}% | prec T1 {r['t1'] / n * 100:.0f}% T2 {r['t2'] / n * 100:.0f}% | rec T2 {self.rec[(d, t)] / max(1, B['t2']) * 100:.0f}%"
                    f" | rest {r['rest'] / n:+.2f}ATR cont {r['cont'] / n * 100:.0f}% rev {r['rev'] / n * 100:.0f}% | T2 era "
                    + "/".join(f"{x[0] / max(1, x[1]) * 100:.0f}" for x in r["e2"]))
