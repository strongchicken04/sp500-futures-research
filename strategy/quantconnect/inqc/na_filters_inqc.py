# region imports
from AlgorithmImports import *
import math
from collections import deque
# endregion
#
# NOISE AREA + TREND-DAY FILTERS (owner 2026-11-22: "how much would a filter that recognises trend days
# help the Noise Area?"). NQ minute 2010-2026 INSIDE QuantConnect, aggregates only. Base = NA30 of
# trend_follow_inqc.py (k 1, checks every 30 min 10:00-15:30 ET, trail max(UB, VWAP) / min(LB, VWAP),
# fills at the mark close, flat 15:59, $15 per NQ trade). FIXED BEFORE RESULTS - filters on ENTRIES only:
#   ER      day efficiency ratio |p - O| / path since the open >= its 60th pct at the mark (last 60 days)
#   NA15    entry needs p beyond the 1.5 x sigma boundary (exits unchanged)
#   RVOL    cumulative RTH volume at the mark >= 1.2 x its 20-day mean at the mark
#   OVN     overnight range (18:00 ET - 09:30 ET) >= its 20-day mean (day filter)
#   VWP     >= 80% of the RTH minute closes so far on the trade side of the VWAP
#   ADX     ADX(14) on 5-min candles >= 25 and +DI / -DI agree with the trade
#   LATE11  entries only from 11:00
# Ceiling (ex post, not tradable): BASE profit split by day type: T1 days (|C - O| >= 0.6 x RTH range) vs
#   the rest; T2 = T1 and |C - O| >= 0.75 x ATR20.
# Stats: trades / yr, win, $ / trade per NQ at today's price, t, $ / yr, max DD, long / short, eras; Lucid
#   25K eval + funded (payout $1,000) on real points, last 6 years, 1 and 2 MNQ.

START = (2010, 1, 1)
END = (2026, 12, 31)
PRICE, PV, COST = 28530.0, 20.0, 15.0
ERAS = ((2010, 2013), (2014, 2017), (2018, 2021), (2022, 2026))
RECENT = date(2020, 11, 20)
MARKS = set(range(10 * 60, 15 * 60 + 31, 30))
VARS = ("BASE", "ER", "NA15", "RVOL", "OVN", "VWP", "ADX", "LATE11")


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



class V:
    def __init__(self, k):
        self.k = k
        self.pos = None
        self.trades = []         # (usd, dir, era, year, date, pts)


class NAFilters(QCAlgorithm):

    def initialize(self):
        self.set_start_date(*START)
        self.set_end_date(*END)
        self.set_cash(1_000_000)
        self.f = self.add_future(Futures.Indices.NASDAQ_100_E_MINI, Resolution.MINUTE, fill_forward=False,
                                 data_normalization_mode=DataNormalizationMode.RAW,
                                 data_mapping_mode=DataMappingMode.OPEN_INTEREST,
                                 contract_depth_offset=0, extended_market_hours=True)
        self.f.set_filter(0, 180)
        self.v = {k: V(k) for k in VARS}
        self.hist = {}
        self.erh = {mm: deque(maxlen=60) for mm in MARKS}
        self.volh = {mm: deque(maxlen=20) for mm in MARKS}
        self.onr = deque(maxlen=20)
        self.rngs = deque(maxlen=20)
        self.adx5 = ADX(14)
        self.b5 = None
        self.mapped = None
        self.day = None
        self.prevC = None
        self.cal = []
        self.daytype = {}        # date -> (t1, t2)
        self.onh = self.onl = None
        self.on_today = None
        self.on_reset = False
        self.on_ok = False
        self._new()

    def _new(self):
        self.O = None
        self.H = self.L = None
        self.pv = self.vv = 0.0
        self.cumv = 0.0
        self.path = 0.0
        self.today = {}
        self.lastC = None
        self.above = self.below = self.nmin = 0
        self.bad = False
        self.er_today = {}
        self.vol_today = {}

    def _book(self, v, px, t):
        p = v.pos
        pts = (px - p["e"]) * p["d"]
        v.trades.append((pts * PRICE / p["e"] * PV - COST, p["d"], era_of(t.year), t.year, t.date(), pts))
        v.pos = None

    def _end_day(self):
        if self.day is None or self.O is None:
            return
        if not self.bad:
            for mm, x in self.today.items():
                self.hist.setdefault(mm, deque(maxlen=14)).append(x)
            for mm, x in self.er_today.items():
                self.erh[mm].append(x)
            for mm, x in self.vol_today.items():
                self.volh[mm].append(x)
            if len(self.rngs) == 20 and self.H is not None:
                atr = sum(self.rngs) / 20.0
                body = abs(self.lastC - self.O)
                t1 = self.H > self.L and body >= 0.6 * (self.H - self.L)
                self.daytype[self.day] = (t1, t1 and body >= 0.75 * atr)
            if self.H is not None:
                self.rngs.append(self.H - self.L)
            self.prevC = self.lastC
        else:
            self.prevC = None

    def on_data(self, data: Slice):
        bar = data.bars.get(self.f.symbol)
        if bar is None:
            return
        t = self.time
        m = t.hour * 60 + t.minute
        o, h, l, c, vol = float(bar.open), float(bar.high), float(bar.low), float(bar.close), float(bar.volume)
        b = self.b5
        self.b5 = [o, h, l, c] if b is None else [b[0], max(b[1], h), min(b[2], l), c]
        if m % 5 == 0:
            bb = self.b5
            self.adx5.update(bb[1], bb[2], bb[3])
            self.b5 = None
        rolled = self.mapped is not None and self.f.mapped != self.mapped
        self.mapped = self.f.mapped
        # overnight range 18:00 ET -> 09:30 ET
        if m > 18 * 60 or m <= 9 * 60 + 30:
            if m > 18 * 60 and (self.onh is None or self.on_reset):
                self.onh, self.onl = h, l
                self.on_reset = False
            elif self.onh is not None:
                self.onh, self.onl = max(self.onh, h), min(self.onl, l)
        if not (9 * 60 + 30 < m <= 16 * 60):
            return
        if self.day != t.date():
            for v in self.v.values():
                if v.pos is not None:
                    self._book(v, self.lastC if self.lastC else o, t)
            self._end_day()
            self.day = t.date()
            self._new()
            if t.date() >= RECENT:
                self.cal.append(t.date())
            # overnight range of this morning
            self.on_today = (self.onh - self.onl) if self.onh is not None else None
            self.on_ok = self.on_today is not None and len(self.onr) == 20 and self.on_today >= sum(self.onr) / 20.0
            if self.on_today is not None:
                self.onr.append(self.on_today)
            self.on_reset = True
        if rolled:
            self.bad = True
            for v in self.v.values():
                if v.pos is not None:
                    self._book(v, c, t)
        if self.O is None:
            self.O = o
            self.H, self.L = h, l
        self.H, self.L = max(self.H, h), min(self.L, l)
        if self.lastC is not None:
            self.path += abs(c - self.lastC)
        self.lastC = c
        self.pv += (h + l + c) / 3.0 * vol
        self.vv += vol
        self.cumv += vol
        vw = self.pv / self.vv if self.vv > 0 else c
        self.nmin += 1
        self.above += c > vw
        self.below += c < vw
        self.today[m] = abs(c / self.O - 1.0)
        er = abs(c - self.O) / self.path if self.path > 0 else 0.0
        if m in MARKS:
            self.er_today[m] = er
            self.vol_today[m] = self.cumv
        if self.bad or self.prevC is None:
            return
        hq = self.hist.get(m)
        if hq is None or len(hq) < 14:
            return
        s = sum(hq) / 14.0
        ub = max(self.O, self.prevC) * (1 + s)
        lb = min(self.O, self.prevC) * (1 - s)
        for k, v in self.v.items():
            if v.pos is not None:
                if m >= 15 * 60 + 59:
                    self._book(v, c, t)
                    continue
                if m in MARKS:
                    p = v.pos
                    if (p["d"] == 1 and c < max(ub, vw)) or (p["d"] == -1 and c > min(lb, vw)):
                        self._book(v, c, t)
            if v.pos is not None or m not in MARKS or m >= 15 * 60 + 59:
                continue
            d = 1 if c > ub else (-1 if c < lb else 0)
            if d == 0:
                continue
            ok = True
            if k == "ER":
                eh = self.erh[m]
                ok = len(eh) == 60 and er >= sorted(eh)[int(0.6 * 60)]
            elif k == "NA15":
                ok = (d == 1 and c > max(self.O, self.prevC) * (1 + 1.5 * s)) or (d == -1 and c < min(self.O, self.prevC) * (1 - 1.5 * s))
            elif k == "RVOL":
                vh = self.volh[m]
                ok = len(vh) == 20 and self.cumv >= 1.2 * sum(vh) / 20.0
            elif k == "OVN":
                ok = self.on_ok
            elif k == "VWP":
                ok = (d == 1 and self.above >= 0.8 * self.nmin) or (d == -1 and self.below >= 0.8 * self.nmin)
            elif k == "ADX":
                a = self.adx5
                ok = a.ready() and a.adx >= 25 and ((d == 1 and a.pdm > a.ndm) or (d == -1 and a.ndm > a.pdm))
            elif k == "LATE11":
                ok = m >= 11 * 60
            if ok:
                v.pos = {"d": d, "e": c}

    def _days(self, tr):
        byd = {}
        for x in tr:
            if x[4] >= RECENT:
                byd.setdefault(x[4], []).append(x[5])
        return [byd.get(d, []) for d in sorted(set(self.cal))]

    def _eval(self, seq, s0, n):
        i, ev = s0, 1
        bal = peak = best = 0.0
        td = 0
        while i < len(seq) and i - s0 < 250:
            day = seq[i]
            i += 1
            if not day:
                continue
            line = 100.0 if peak >= 1100.0 else peak - 1000.0
            run = bal
            dead = False
            for pts in day:
                run += pts * 2.0 * n - 2.5 * n
                if run <= line:
                    dead = True
                    break
            if dead:
                ev += 1
                bal = peak = best = 0.0
                td = 0
                continue
            td += 1
            best = max(best, run - bal)
            bal = run
            peak = max(peak, bal)
            if bal >= 1250.0 and best <= 0.5 * bal and td >= 2:
                return i - s0, ev, True
        return i - s0, ev, False

    def _funded(self, seq, s0, n):
        bal = peak = paid = 0.0
        locked = False
        wd = npay = 0
        i = s0
        while i < len(seq) and i - s0 < 500:
            day = seq[i]
            i += 1
            line = 100.0 if locked else peak - 1000.0
            run = bal
            for pts in day:
                run += pts * 2.0 * n - 2.5 * n
                if run <= line:
                    return paid, npay, i - s0
            if run - bal >= 100.0:
                wd += 1
            bal = run
            peak = max(peak, bal)
            if peak >= 1100.0:
                locked = True
            amt = min(0.5 * bal, 1000.0)
            if wd >= 5 and amt >= 1000.0:
                bal -= amt
                paid += 0.9 * amt
                npay += 1
                wd = 0
                locked = True
        return paid, npay, i - s0

    def on_end_of_algorithm(self):
        self._end_day()
        for k, v in self.v.items():
            tr = v.trades
            n = len(tr)
            if n < 20:
                continue
            yrs = max(1.0, len(set(x[3] for x in tr)))
            u = [x[0] for x in tr]
            mu = sum(u) / n
            sd = math.sqrt(sum((x - mu) ** 2 for x in u) / (n - 1))
            cum = pk = mdd = 0.0
            for x in u:
                cum += x
                pk = max(pk, cum)
                mdd = min(mdd, cum - pk)
            lo = [x[0] for x in tr if x[1] == 1]
            sh = [x[0] for x in tr if x[1] == -1]
            era = " ".join(f"{sum(x[0] for x in tr if x[2] == i) / max(1, sum(1 for x in tr if x[2] == i)):+.0f}" for i in range(len(ERAS)))
            self.set_runtime_statistic(f"NF {k}",
                f"{n / yrs:.0f}/y win {sum(1 for x in u if x > 0) / n * 100:.0f}% ${mu:+.0f}/tr t{mu / (sd / math.sqrt(n)):+.1f} ${sum(u) / yrs:+,.0f}/y DD ${mdd:,.0f}"
                f" | L {sum(lo) / max(1, len(lo)):+.0f} S {sum(sh) / max(1, len(sh)):+.0f} | era {era}")
            seq = self._days(tr)
            cells = []
            for nm in (1, 2):
                res = [self._eval(seq, s0, nm) for s0 in range(0, max(1, len(seq) - 120))]
                ok = [r for r in res if r[2]]
                ev = f"{len(ok) / sum(r[1] for r in res) * 100:.0f}%/{sum(r[0] for r in ok) / len(ok):.0f}d" if ok else "0%"
                fr = [self._funded(seq, s0, nm) for s0 in range(0, max(1, len(seq) - 120), 3)]
                kk = len(fr)
                cells.append(f"{nm}MNQ eval {ev} funded ${sum(r[0] for r in fr) / kk:,.0f} {sum(1 for r in fr if r[1] > 0) / kk * 100:.0f}% {sum(r[2] for r in fr) / kk:.0f}d")
            self.set_runtime_statistic(f"NF {k} lucid", " | ".join(cells))
            if k == "BASE":
                yrs_ = yrs
                parts = []
                for lab, sel in (("T1", lambda dt: dt[0]), ("T2", lambda dt: dt[1]), ("nonT1", lambda dt: not dt[0])):
                    sub = [x[0] for x in tr if x[4] in self.daytype and sel(self.daytype[x[4]])]
                    parts.append(f"{lab} {len(sub) / yrs_:.0f}/y ${sum(sub) / max(1, len(sub)):+.0f}/tr ${sum(sub) / yrs_:+,.0f}/y")
                self.set_runtime_statistic("NF ceiling (ex post)", " | ".join(parts))
