# region imports
from AlgorithmImports import *
import math
from collections import deque
# endregion
#
# OVERNIGHT BIAS ORB (S3) - v2 controls + Lucid evaluation sims (2026-11-12), NQ minute
# 2010-2026 INSIDE QuantConnect, aggregates only. Rules as in vwap_adx_onorb_inqc.py main:
# overnight 23:00-08:30 CT, bias = 08:30 CT open in the top / bottom third, OR = 08:30-08:45
# CT candle, a 15-min close beyond the OR in the bias direction with ADX(14, 15m) > 20 ->
# entry at the next minute open, SL = 0.30 x 15-day mean daily range (00:00-16:00 CT),
# TP = 3 x SL, flat 14:30 CT, one trade a day. FIXED BEFORE RESULTS:
#   MAIN-L / MAIN-S  long / short split of MAIN
#   BIASONLY  enter at the 08:45 CT candle close in the bias direction (no break, no ADX)
#   LONGDRIFT long every day at the 08:45 CT close, same SL / TP (plain drift)
#   Eras + per-year $ and the last 6 years (from 2020-11-12).
# Lucid sims on REAL points (no re-scaling), last 6 years, one trade a day, every start day:
#   25K: +$1,250, DD $1,000 EOD trailing (locks +$100 at peak $1,100), best day <= 50%, fee $60,
#        MNQ cap 20. 50K: +$3,000, DD $2,000 (locks +$100 at $2,100), fee $90, MNQ cap 40.
#   Sizing FIXn MNQ, or RISKx = floor(x / (SL pt x $2 + $2.50)) MNQ (>= 1). MNQ $2/pt,
#   $2.50 per MNQ round trip. Intraday breach on the trade's worst point is not modelled
#   (closed-trade P&L; a stop is the worst case for a single trade a day).

START = (2010, 1, 1)
END = (2026, 12, 31)
PRICE, PV, COST = 28530.0, 20.0, 15.0
ERAS = ((2010, 2013), (2014, 2017), (2018, 2021), (2022, 2026))
RECENT = (2020, 11, 12)


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


class Run:
    def __init__(self, key):
        self.key = key
        self.trades = []        # (pts_gross, sl_pts, r_net, usd_scaled, era, year, date, dir)
        self.pending = None
        self.pos = None
        self.done = False


class ONORBEval(QCAlgorithm):

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
        self.b15 = None
        self.runs = {k: Run(k) for k in ("MAIN", "BIASONLY", "LONGDRIFT")}
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
        b = self.b15
        self.b15 = [o, h, l, c] if b is None else [b[0], max(b[1], h), min(b[2], l), c]
        close15 = (m % 15 == 0)
        if close15:
            bb = self.b15
            self.adx15.update(bb[1], bb[2], bb[3])
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
            if r.done or r.pos is not None or not close15 or not (9 * 60 + 45 <= m <= 15 * 60 + 15):
                continue
            if self.or15 is None or self.ropen is None or self.onh is None or len(self.rng) < 15:
                continue
            hi, lo = self.onh, self.onl
            q = (self.ropen - lo) / (hi - lo) if hi > lo else 0.5
            bias = 1 if q >= 2 / 3 else (-1 if q <= 1 / 3 else 0)
            sld = 0.30 * sum(self.rng) / 15.0
            d = 0
            if key == "MAIN":
                if m > 9 * 60 + 45 and self.adx15.ready() and self.adx15.adx > 20:
                    if bias == 1 and c > self.or15[0]:
                        d = 1
                    elif bias == -1 and c < self.or15[1]:
                        d = -1
            elif m == 9 * 60 + 45:
                d = bias if key == "BIASONLY" else 1
                if d == 0:
                    r.done = True
            if d != 0:
                r.pending = (d, sld)
                r.done = True

    # ------------------------------------------------------------------ helpers
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
                f"{sum(x[2] for x in tr) / n:+.3f}R ${mu:+.0f}/tr t{(mu / (sd / math.sqrt(n)) if sd > 0 else 0):+.1f} DD ${mdd:,.0f} | R by era {era}")

    def _chain(self, seq, s0, T, DD, cap, scheme):
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
            if scheme.startswith("FIX"):
                n = int(scheme[3:])
            else:
                n = int(float(scheme[4:]) / (sl * 2.0 + 2.5))
            n = max(1, min(cap, n))
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

    def _evals(self, tr, T, DD, cap, fee, schemes):
        byd = {x[6]: (x[0], x[1]) for x in tr if x[6] >= date(*RECENT)}
        cal = sorted(set(self.cal))
        seq = [byd.get(d) for d in cal]
        out = []
        for sc in schemes:
            res = [self._chain(seq, s0, T, DD, cap, sc) for s0 in range(0, max(0, len(seq) - 120))]
            ok = [r for r in res if r[2]]
            if not res or not ok:
                out.append(f"{sc} none")
                continue
            ppa = len(ok) / sum(r[1] for r in res) * 100
            dd = sum(r[0] for r in ok) / len(ok)
            out.append(f"{sc} {ppa:.0f}%/{dd:.0f}d/${sum(r[1] for r in res) / len(res) * fee:.0f}")
        return " | ".join(out)

    def on_end_of_algorithm(self):
        for r in self.runs.values():
            if r.pos is not None:
                self._book(r, r.pos["e"], self.time)
        mt = self.runs["MAIN"].trades
        for key, r in self.runs.items():
            if len(r.trades) >= 10:
                self.set_runtime_statistic(f"O {key}", self._summ(r.trades))
        for d, lab in ((1, "MAIN-L"), (-1, "MAIN-S")):
            sub = [x for x in mt if x[7] == d]
            if len(sub) >= 10:
                self.set_runtime_statistic(f"O {lab}", self._summ(sub))
        rec = [x for x in mt if x[6] >= date(*RECENT)]
        if len(rec) >= 10:
            self.set_runtime_statistic("O MAIN last6y", self._summ(rec) + f" | mean SL {sum(x[1] for x in rec) / len(rec):.0f}pt")
        ys = sorted(set(x[5] for x in mt))
        self.set_runtime_statistic("O MAIN years R", " ".join(f"{y % 100}:{sum(x[2] for x in mt if x[5] == y):+.0f}" for y in ys))
        self.set_runtime_statistic("O MAIN SL pts by year", " ".join(f"{y % 100}:{sum(x[1] for x in mt if x[5] == y) / max(1, sum(1 for x in mt if x[5] == y)):.0f}" for y in ys if y >= 2020))
        self.set_runtime_statistic("E25 a", self._evals(mt, 1250.0, 1000.0, 20, 60, ("FIX1", "FIX2", "FIX3", "FIX4")))
        self.set_runtime_statistic("E25 b", self._evals(mt, 1250.0, 1000.0, 20, 60, ("RISK250", "RISK350", "RISK450", "RISK600")))
        self.set_runtime_statistic("E50 a", self._evals(mt, 3000.0, 2000.0, 40, 90, ("FIX2", "FIX3", "FIX4", "FIX6")))
        self.set_runtime_statistic("E50 b", self._evals(mt, 3000.0, 2000.0, 40, 90, ("RISK500", "RISK700", "RISK900", "RISK1200")))
        self.set_runtime_statistic("O info", f"cal {len(self.cal)} days, MAIN recent trades {len(rec)}")
