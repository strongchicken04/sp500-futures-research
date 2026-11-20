# region imports
from AlgorithmImports import *
import math
from collections import deque
# endregion
#
# NEXT-HOUR TREND IDENTIFICATION (owner 2026-11-20: "can we reliably tell we are in a trend just for the next
# hour?"). NQ minute 2010-2026 INSIDE QuantConnect, aggregates only. FIXED BEFORE RESULTS:
# Decision times tau = 10:30, 11:00, ..., 15:00 ET (bar-end clock), data up to tau only.
# Truth for the next 60 minutes (tau..tau+60): net = C(tau+60) - C(tau), rng = high - low of those minutes,
#   ATRh(tau) = mean 60-minute range of the same window over the previous 20 days.
#   H1 trend hour: |net| >= 0.6 x rng; H2 strong trend hour: H1 and |net| >= 1.0 x ATRh; direction sign(net).
# Detectors (direction d):
#   NA / NA15  day Noise Area state at tau (sigma = 14-day mean |p/O - 1| at tau, gap-adjusted, 1x / 1.5x)
#   ADX        ADX(14) on 5-min candles >= 25, d = sign(+DI - -DI)
#   ER60       efficiency ratio of the last 60 minutes >= its 80th pct at tau (60 days), d = sign of the move
#   ERDAY      efficiency ratio since the open >= its 80th pct at tau, d = sign(p - O)
#   PREVH      the previous 60 minutes were an H2 hour, d = its direction
#   VWP60      >= 80% of the last 60 minute closes on one side of the RTH VWAP and p on that side
#   MOM60      |60-minute return| >= its 80th pct at tau, d = its sign
#   STAIR      the last 4 completed 15-min candles have rising highs AND rising lows (d = +1) or falling (-1)
#   NA15+ER60  both agree
# Metrics pooled over all decision times: detection rate, precision of H1 / H2 in the detected direction vs
#   the base rates, mean next-hour move in direction (ATRh units), continuation >= +0.25 ATRh vs reversal
#   <= -0.25 ATRh, H2 precision by era. Days with a contract roll inside RTH are skipped.

START = (2010, 1, 1)
END = (2026, 12, 31)
TAUS = tuple(range(10 * 60 + 30, 15 * 60 + 1, 30))
DETS = ("NA", "NA15", "ADX", "ER60", "ERDAY", "PREVH", "VWP60", "MOM60", "STAIR", "NA15+ER60")
ERAS = ((2010, 2013), (2014, 2017), (2018, 2021), (2022, 2026))


def era_of(y):
    for i, (a, b) in enumerate(ERAS):
        if a <= y <= b:
            return i
    return None


def pct80(dq):
    s = sorted(dq)
    return s[int(0.8 * len(s))]


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



class NextHour(QCAlgorithm):

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
        self.atrh = {t: deque(maxlen=20) for t in range(9 * 60 + 30, 15 * 60 + 1, 30)}
        self.sig = {t: deque(maxlen=14) for t in TAUS}
        self.er60h = {t: deque(maxlen=60) for t in TAUS}
        self.erdh = {t: deque(maxlen=60) for t in TAUS}
        self.momh = {t: deque(maxlen=60) for t in TAUS}
        self.res = {d: {"n": 0, "h1": 0, "h2": 0, "mv": 0.0, "cont": 0, "rev": 0, "e2": [[0, 0] for _ in ERAS]} for d in DETS}
        self.base = {"n": 0, "h1": 0, "h2": 0}
        self._new()

    def _new(self):
        self.bars = []          # (m, h, l, c)
        self.O = None
        self.pv = self.vv = 0.0
        self.path = 0.0
        self.lastc = None
        self.side = []          # +1 / -1 / 0 per minute vs VWAP
        self.snap = {}
        self.bad = False
        self.c15 = []           # completed 15-min RTH candles (h, l)
        self.b15 = None

    def _win(self, t0, t1):
        xs = [b for b in self.bars if t0 < b[0] <= t1]
        if not xs:
            return None
        return max(b[1] for b in xs), min(b[2] for b in xs), xs[-1][3]

    def _close_day(self):
        if self.day is None or self.bad or not self.bars:
            return
        cmap = {b[0]: b[3] for b in self.bars}
        e = era_of(self.day.year)
        for t, (p, dets, atrh) in self.snap.items():
            w = self._win(t, t + 60)
            if w is None or atrh is None or (t + 60) not in cmap:
                continue
            hh, ll, c1 = w
            net = c1 - p
            rng = max(hh, p) - min(ll, p)
            ndir = 1 if net > 0 else -1
            h1 = rng > 0 and abs(net) >= 0.6 * rng
            h2 = h1 and abs(net) >= atrh
            self.base["n"] += 1
            self.base["h1"] += h1
            self.base["h2"] += h2
            for d, dr in dets.items():
                if dr == 0:
                    continue
                r = self.res[d]
                r["n"] += 1
                r["h1"] += h1 and ndir == dr
                ok2 = h2 and ndir == dr
                r["h2"] += ok2
                mv = net * dr / atrh
                r["mv"] += mv
                r["cont"] += mv >= 0.25
                r["rev"] += mv <= -0.25
                if e is not None:
                    r["e2"][e][1] += 1
                    r["e2"][e][0] += ok2
        # update the 60-minute range history (after the day: used from the next day on)
        for t in self.atrh:
            w = self._win(t, t + 60)
            if w is not None:
                pc = cmap.get(t)
                hh, ll = w[0], w[1]
                if pc is not None:
                    hh, ll = max(hh, pc), min(ll, pc)
                self.atrh[t].append(hh - ll)

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
            if self.day is not None and self.bars and not self.bad:
                self.prevC = self.bars[-1][3]
            self.day = t.date()
            self._new()
        if rolled:
            self.bad = True
            self.prevC = None
        if self.O is None:
            self.O = o
        self.bars.append((m, h, l, c))
        self.pv += (h + l + c) / 3.0 * v
        self.vv += v
        vw = self.pv / self.vv if self.vv > 0 else c
        if self.lastc is not None:
            self.path += abs(c - self.lastc)
        self.lastc = c
        self.side.append(1 if c > vw else (-1 if c < vw else 0))
        b = self.b15
        self.b15 = [h, l] if b is None else [max(b[0], h), min(b[1], l)]
        if m % 15 == 0:
            self.c15.append(tuple(self.b15))
            self.b15 = None
        if m not in TAUS or self.bad or self.prevC is None:
            return
        O = self.O
        dets = {}
        # day Noise Area
        sh = self.sig[m]
        mvd = abs(c / O - 1.0)
        if len(sh) == 14:
            s = sum(sh) / 14.0
            for name, k in (("NA", 1.0), ("NA15", 1.5)):
                up = max(O, self.prevC) * (1 + k * s)
                dn = min(O, self.prevC) * (1 - k * s)
                dets[name] = 1 if c > up else (-1 if c < dn else 0)
        sh.append(mvd)
        a = self.adx5
        if a.ready() and a.tr and a.tr > 0:
            dets["ADX"] = (1 if a.pdm > a.ndm else -1) if a.adx >= 25 else 0
        last = [x for x in self.bars if x[0] > m - 60]
        prev = [x for x in self.bars if x[0] <= m - 60]
        if len(last) >= 50 and prev:
            p0 = prev[-1][3]
            path60 = sum(abs(last[i][3] - (last[i - 1][3] if i else p0)) for i in range(len(last)))
            er60 = abs(c - p0) / path60 if path60 > 0 else 0.0
            eh = self.er60h[m]
            if len(eh) == 60:
                dets["ER60"] = (1 if c > p0 else -1) if er60 >= pct80(eh) else 0
            eh.append(er60)
            r60 = c / p0 - 1.0
            mh = self.momh[m]
            if len(mh) == 60:
                dets["MOM60"] = (1 if r60 > 0 else -1) if abs(r60) >= pct80(mh) else 0
            mh.append(abs(r60))
            # previous hour strong trend (H2 on the last 60 minutes)
            ah = self.atrh.get(m - 60)
            if ah is not None and len(ah) == 20:
                hh = max(max(x[1] for x in last), p0)
                ll = min(min(x[2] for x in last), p0)
                net = c - p0
                dets["PREVH"] = (1 if net > 0 else -1) if (hh > ll and abs(net) >= 0.6 * (hh - ll) and abs(net) >= sum(ah) / 20.0) else 0
            sd = self.side[-60:]
            dets["VWP60"] = 1 if (c > vw and sum(1 for x in sd if x > 0) >= 48) else (-1 if (c < vw and sum(1 for x in sd if x < 0) >= 48) else 0)
        erd = abs(c - O) / self.path if self.path > 0 else 0.0
        edh = self.erdh[m]
        if len(edh) == 60:
            dets["ERDAY"] = (1 if c > O else -1) if erd >= pct80(edh) else 0
        edh.append(erd)
        if len(self.c15) >= 4:
            q = self.c15[-4:]
            if all(q[i][0] > q[i - 1][0] and q[i][1] > q[i - 1][1] for i in range(1, 4)):
                dets["STAIR"] = 1
            elif all(q[i][0] < q[i - 1][0] and q[i][1] < q[i - 1][1] for i in range(1, 4)):
                dets["STAIR"] = -1
            else:
                dets["STAIR"] = 0
        if "NA15" in dets and "ER60" in dets:
            dets["NA15+ER60"] = dets["NA15"] if dets["NA15"] != 0 and dets["NA15"] == dets["ER60"] else 0
        ah = self.atrh[m]
        self.snap[m] = (c, dets, sum(ah) / 20.0 if len(ah) == 20 else None)

    def on_end_of_algorithm(self):
        self._close_day()
        B = self.base
        n = max(1, B["n"])
        self.set_runtime_statistic("NH base", f"decisions {B['n']} | H1 {B['h1'] / n * 100:.0f}% (one direction {B['h1'] / n * 50:.0f}%) | H2 {B['h2'] / n * 100:.0f}% (one direction {B['h2'] / n * 50:.0f}%)")
        for d in DETS:
            r = self.res[d]
            k = r["n"]
            if k < 30:
                continue
            self.set_runtime_statistic(f"NH {d}",
                f"det {k / n * 100:.0f}% | prec H1 {r['h1'] / k * 100:.1f}% H2 {r['h2'] / k * 100:.1f}% | next hour {r['mv'] / k:+.3f} ATRh cont {r['cont'] / k * 100:.0f}% rev {r['rev'] / k * 100:.0f}% | H2 era "
                + "/".join(f"{x[0] / max(1, x[1]) * 100:.0f}" for x in r["e2"]))
