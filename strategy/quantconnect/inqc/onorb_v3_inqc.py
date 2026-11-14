# region imports
from AlgorithmImports import *
import math
from collections import deque
# endregion
#
# OVERNIGHT BIAS ORB v3 - owner restated the rules (2026-11-14), NQ minute 2010-2026 INSIDE
# QuantConnect, aggregates only. Rules (owner): overnight range 23:00-08:30 CT split in equal thirds;
# NY open (08:30 CT) in the top third -> long only that day, bottom third -> short only, middle -> no
# trade. OR = 08:30-08:45 CT. Any 15-min candle after 08:45 CT that CLOSES above the OR high (long day)
# / below the OR low (short day) with ADX >= 20 (either direction) -> entry at the next open. SL = 30% of
# the 15-period moving average of ATR, TP = 3 x risk, all trades closed 14:30 CT. One trade a day
# (owner's earlier statement). Test details FIXED BEFORE RESULTS:
#   ADX(14) on 15-min candles (all hours). ATR basis variants (the timeframe is not stated):
#     DATR  SMA15 of the daily ATR(14) (Wilder), daily bars = full Globex session 17:00-16:00 CT
#     M15   SMA15 of ATR(14) on the 15-min candles (value at the signal candle)
#     RNG   the v1 / v2 basis (15-day mean of the 00:00-16:00 CT range), for continuity
#   Fills: stop first if both in one minute, gaps at the open. $15 per NQ trade.
#   Stats: R, $ per NQ at today's price, eras, years, last 6 years; Lucid 25K eval (+$1,250, DD $1,000
#   EOD trailing locking +$100 at $1,100, best day <= 50%, fee $60) and 25K funded (DD as eval, locked
#   after the first payout; payout = min(50% of profit, $1,000) once 5 days >= $100 and >= $500 is
#   available; 90% kept; 250-day horizon) on real points, last 6 years, MNQ $2/pt + $2.50, cap 20,
#   sizes FIXn MNQ or RISKx = floor(x / (risk pt x 2 + 2.5)).

START = (2010, 1, 1)
END = (2026, 12, 31)
PRICE, PV, COST = 28530.0, 20.0, 15.0
ERAS = ((2010, 2013), (2014, 2017), (2018, 2021), (2022, 2026))
RECENT = (2020, 11, 12)
BASES = ("DATR", "M15", "RNG")


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



class WATR:
    def __init__(self, n):
        self.n = n
        self.pc = None
        self.v = None
        self.k = 0

    def update(self, h, l, c):
        tr = h - l if self.pc is None else max(h - l, abs(h - self.pc), abs(l - self.pc))
        self.v = tr if self.v is None else self.v + (tr - self.v) / self.n
        self.pc = c
        self.k += 1


class Run:
    def __init__(self, key):
        self.key = key
        self.trades = []
        self.pending = None
        self.pos = None
        self.done = False


class ONORB3(QCAlgorithm):

    def initialize(self):
        self.set_start_date(*START)
        self.set_end_date(*END)
        self.set_cash(1_000_000)
        self.f = self.add_future(Futures.Indices.NASDAQ_100_E_MINI, Resolution.MINUTE, fill_forward=False,
                                 data_normalization_mode=DataNormalizationMode.RAW,
                                 data_mapping_mode=DataMappingMode.OPEN_INTEREST,
                                 contract_depth_offset=0, extended_market_hours=True)
        self.f.set_filter(0, 180)
        self.adx15 = ADX(14)
        self.atr15 = WATR(14)
        self.atr15_hist = deque(maxlen=15)
        self.datr = WATR(14)
        self.datr_hist = deque(maxlen=15)
        self.sess = None            # [h, l, c] of the Globex session in progress
        self.b15 = None
        self.runs = {b: Run(b) for b in BASES}
        self.date = None
        self.mapped = None
        self.rng = deque(maxlen=15)
        self.cal = []
        self._new_day()

    def _new_day(self):
        self.onh = self.onl = None
        self.or15 = None
        self.ropen = None
        self.fhi = self.flo = None

    def _book(self, r, px, t):
        p = r.pos
        pts = (px - p["e"]) * p["d"]
        net = pts - COST / PV
        r.trades.append((pts, p["risk"], net / p["risk"], net * PRICE / p["e"] * PV, era_of(t.year), t.year, t.date(), p["d"]))
        r.pos = None

    def on_data(self, data: Slice):
        bar = data.bars.get(self.f.symbol)
        if bar is None:
            return
        t = self.time
        m = t.hour * 60 + t.minute
        o, h, l, c = float(bar.open), float(bar.high), float(bar.low), float(bar.close)
        # Globex session bars (18:00 ET -> 17:00 ET) for the daily ATR
        if m > 18 * 60 or m <= 17 * 60:
            if m > 18 * 60 and self.sess is not None and self.sess[3] != t.date():
                self.datr.update(self.sess[0], self.sess[1], self.sess[2])
                if self.datr.k >= 14:
                    self.datr_hist.append(self.datr.v)
                self.sess = None
            if self.sess is None:
                self.sess = [h, l, c, t.date()]
            else:
                self.sess = [max(self.sess[0], h), min(self.sess[1], l), c, self.sess[3]]
        b = self.b15
        self.b15 = [o, h, l, c] if b is None else [b[0], max(b[1], h), min(b[2], l), c]
        close15 = (m % 15 == 0)
        if close15:
            bb = self.b15
            self.adx15.update(bb[1], bb[2], bb[3])
            self.atr15.update(bb[1], bb[2], bb[3])
            if self.atr15.k >= 14:
                self.atr15_hist.append(self.atr15.v)
            self.b15 = None
        if 0 < m <= 17 * 60 and self.date != t.date():
            if self.date is not None and self.fhi is not None:
                self.rng.append(self.fhi - self.flo)
            self.date = t.date()
            self.mapped = self.f.mapped
            self._new_day()
            for r in self.runs.values():
                if r.pos is not None:
                    self._book(r, c, t)
                r.pending = None
                r.done = False
        if self.date != t.date() or not (0 < m <= 17 * 60):
            return
        if self.f.mapped != self.mapped:
            for r in self.runs.values():
                if r.pos is not None:
                    self._book(r, c, t)
                r.pending = None
                r.done = True
            self.mapped = self.f.mapped
        if 60 < m <= 17 * 60:
            self.fhi = h if self.fhi is None else max(self.fhi, h)
            self.flo = l if self.flo is None else min(self.flo, l)
        if m <= 9 * 60 + 30:
            self.onh = h if self.onh is None else max(self.onh, h)
            self.onl = l if self.onl is None else min(self.onl, l)
        if 9 * 60 + 30 < m <= 16 * 60:
            if self.ropen is None:
                self.ropen = o
                if t.date() >= date(*RECENT):
                    self.cal.append(t.date())
            if m <= 9 * 60 + 45:
                self.or15 = [h, l] if self.or15 is None else [max(self.or15[0], h), min(self.or15[1], l)]
        tex = 15 * 60 + 30
        for key, r in self.runs.items():
            if r.pending is not None and r.pos is None:
                d, sld = r.pending
                r.pending = None
                r.pos = {"d": d, "e": o, "sl": o - d * sld, "tp": o + d * 3 * sld, "risk": sld}
            p = r.pos
            if p is not None:
                if p["d"] == 1:
                    if l <= p["sl"]:
                        self._book(r, min(p["sl"], o), t)
                    elif h >= p["tp"]:
                        self._book(r, max(p["tp"], o), t)
                else:
                    if h >= p["sl"]:
                        self._book(r, max(p["sl"], o), t)
                    elif l <= p["tp"]:
                        self._book(r, min(p["tp"], o), t)
                if r.pos is not None and m >= tex:
                    self._book(r, c, t)
            if r.done or r.pos is not None or not close15 or not (9 * 60 + 45 < m <= 15 * 60 + 15):
                continue
            if self.or15 is None or self.ropen is None or self.onh is None:
                continue
            if key == "DATR":
                if len(self.datr_hist) < 15:
                    continue
                base = sum(self.datr_hist) / 15.0
            elif key == "M15":
                if len(self.atr15_hist) < 15:
                    continue
                base = sum(self.atr15_hist) / 15.0
            else:
                if len(self.rng) < 15:
                    continue
                base = sum(self.rng) / 15.0
            hi, lo = self.onh, self.onl
            q = (self.ropen - lo) / (hi - lo) if hi > lo else 0.5
            bias = 1 if q >= 2 / 3 else (-1 if q <= 1 / 3 else 0)
            if bias == 0:
                r.done = True
                continue
            if not (self.adx15.ready() and self.adx15.adx >= 20):
                continue
            d = 0
            if bias == 1 and c > self.or15[0]:
                d = 1
            elif bias == -1 and c < self.or15[1]:
                d = -1
            if d != 0:
                r.pending = (d, 0.30 * base)
                r.done = True

    def _summ(self, tr):
        n = len(tr)
        yrs = max(1.0, len(set(x[5] for x in tr)))
        usd = [x[3] for x in tr]
        mu = sum(usd) / n
        sd = math.sqrt(sum((x - mu) ** 2 for x in usd) / (n - 1)) if n > 1 else 0
        cum = pk = mdd = 0.0
        for x in usd:
            cum += x
            pk = max(pk, cum)
            mdd = min(mdd, cum - pk)
        era = " ".join(f"{sum(x[2] for x in tr if x[4] == i) / max(1, sum(1 for x in tr if x[4] == i)):+.2f}" for i in range(len(ERAS)))
        tp = sum(1 for x in tr if x[0] >= 2.99 * x[1]) / n * 100
        slh = sum(1 for x in tr if x[0] <= -0.99 * x[1]) / n * 100
        return (f"{n / yrs:.0f}/y win {sum(1 for x in tr if x[0] > 0) / n * 100:.0f}% TP {tp:.0f}% SL {slh:.0f}% "
                f"{sum(x[2] for x in tr) / n:+.3f}R ${mu:+.0f}/tr t{(mu / (sd / math.sqrt(n)) if sd > 0 else 0):+.1f} DD ${mdd:,.0f} | R era {era}")

    def _size(self, scheme, sl):
        if scheme.startswith("FIX"):
            n = int(scheme[3:])
        else:
            n = int(float(scheme[4:]) / (sl * 2.0 + 2.5))
        return max(1, min(20, n))

    def _chain(self, seq, s0, scheme):
        T, DD = 1250.0, 1000.0
        i, ev = s0, 1
        eq = peak = best = 0.0
        td = 0
        while i < len(seq) and i - s0 < 250:
            day = seq[i]
            i += 1
            if day is None:
                continue
            pts, sl = day
            line = 100.0 if peak >= DD + 100.0 else peak - DD
            n = self._size(scheme, sl)
            run = eq + pts * 2.0 * n - 2.5 * n
            td += 1
            if run <= line:
                ev += 1
                eq = peak = best = 0.0
                td = 0
                continue
            best = max(best, run - eq)
            eq = run
            peak = max(peak, eq)
            if eq >= T and best <= 0.5 * eq and td >= 2:
                return i - s0, ev, True
        return i - s0, ev, False

    def _funded(self, seq, s0, scheme):
        bal = peak = paid = 0.0
        locked = False
        wd = npay = 0
        i = s0
        while i < len(seq) and i - s0 < 250:
            day = seq[i]
            i += 1
            line = 100.0 if locked else peak - 1000.0
            run = bal
            if day is not None:
                pts, sl = day
                n = self._size(scheme, sl)
                run += pts * 2.0 * n - 2.5 * n
                if run <= line:
                    return paid, npay, True
            if run - bal >= 100.0:
                wd += 1
            bal = run
            peak = max(peak, bal)
            if peak >= 1100.0:
                locked = True
            amt = min(0.5 * bal, 1000.0)
            if wd >= 5 and amt >= 500.0:
                bal -= amt
                paid += 0.9 * amt
                npay += 1
                wd = 0
                locked = True
        return paid, npay, False

    def _seq(self, tr):
        byd = {x[6]: (x[0], x[1]) for x in tr if x[6] >= date(*RECENT)}
        return [byd.get(d) for d in sorted(set(self.cal))]

    def _evals(self, tr, schemes):
        seq = self._seq(tr)
        out = []
        for sc in schemes:
            res = [self._chain(seq, s0, sc) for s0 in range(0, max(0, len(seq) - 120))]
            ok = [r for r in res if r[2]]
            if not ok:
                out.append(f"{sc} 0%")
                continue
            out.append(f"{sc} {len(ok) / sum(r[1] for r in res) * 100:.0f}%/{sum(r[0] for r in ok) / len(ok):.0f}d/${sum(r[1] for r in res) / len(res) * 60:.0f}")
        return " | ".join(out)

    def _fund(self, tr, schemes):
        seq = self._seq(tr)
        starts = range(0, max(1, len(seq) - 250), 5)
        out = []
        for sc in schemes:
            res = [self._funded(seq, s0, sc) for s0 in starts]
            nn = len(res)
            out.append(f"{sc} ${sum(r[0] for r in res) / nn:.0f} {sum(1 for r in res if r[1] > 0) / nn * 100:.0f}%")
        return " | ".join(out)

    def on_end_of_algorithm(self):
        for r in self.runs.values():
            if r.pos is not None:
                self._book(r, r.pos["e"], self.time)
        for key, r in self.runs.items():
            tr = r.trades
            if len(tr) < 10:
                continue
            self.set_runtime_statistic(f"O3 {key}", self._summ(tr))
            for d, lab in ((1, "L"), (-1, "S")):
                sub = [x for x in tr if x[7] == d]
                if len(sub) >= 10:
                    self.set_runtime_statistic(f"O3 {key} {lab}", self._summ(sub))
            rec = [x for x in tr if x[6] >= date(*RECENT)]
            if len(rec) >= 10:
                rs = sorted(x[1] for x in rec)
                self.set_runtime_statistic(f"O3 {key} last6y", self._summ(rec) + f" | SL med {rs[len(rs) // 2]:.0f}pt")
            ys = sorted(set(x[5] for x in tr))
            self.set_runtime_statistic(f"O3 {key} years R", " ".join(f"{y % 100}:{sum(x[2] for x in tr if x[5] == y):+.0f}" for y in ys))
            self.set_runtime_statistic(f"O3 {key} SL pt by year", " ".join(f"{y % 100}:{sum(x[1] for x in tr if x[5] == y) / max(1, sum(1 for x in tr if x[5] == y)):.0f}" for y in ys if y >= 2020))
            sch = ("FIX1", "FIX2", "FIX4", "RISK150", "RISK250", "RISK350", "RISK500")
            self.set_runtime_statistic(f"E25 {key}", self._evals(tr, sch))
            self.set_runtime_statistic(f"F25 {key}", self._fund(tr, sch))
