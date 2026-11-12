# region imports
from AlgorithmImports import *
import math
from collections import deque
# endregion
#
# S2 "VWAP PULLBACK + ADX" - exit variants (owner 2026-11-12: "could the pullback work on props?
# try"). Entry unchanged from vwap_adx_onorb_inqc.py (ADX 14 on 1-min, VWAP from 08:30 CT,
# OR 08:30-09:00 CT, 1-min close above OR high -> touch VWAP -> close back above -> ADX > 20
# and not rising -> entry at the next minute open), FIRST signal of the day only.
# Exits FIXED BEFORE RESULTS (time exit 14:55 CT = 15:55 ET for all):
#   LIT     SL = low of last 20 candles, TP = high of last 5 (owner, control; skip if TP <= entry)
#   R1/R15/R2  SL = low of last 20, TP = entry + 1 / 1.5 / 2 x risk
#   T1/T2   SL = pullback low (lowest low from the first VWAP touch to the signal) - 1 tick,
#           TP = 1 / 2 x risk
#   HOLD    SL = low of last 20, no TP
#   NOSTOP  no SL, no TP (does the entry have direction at all?)
#   DRIFT   control: long every day at 10:30 CT (11:30 ET) to 14:55 CT
# Costs $15 per NQ trade. Stats: R (net / risk), $ per NQ at today's price, eras, mean risk pt.
# Lucid 25K (last 6 years, real points): +$1,250, $1,000 EOD trailing DD locking +$100 at $1,100,
#   best day <= 50%, fee $60, MNQ $2/pt + $2.50 round trip, cap 20 MNQ; size RISKx =
#   floor(x / (risk pt x 2 + 2.5)); NOSTOP / DRIFT use FIXn MNQ.

START = (2010, 1, 1)
END = (2026, 12, 31)
PRICE, PV, COST = 28530.0, 20.0, 15.0
ERAS = ((2010, 2013), (2014, 2017), (2018, 2021), (2022, 2026))
RECENT = (2020, 11, 12)
EXITS = ("LIT", "R1", "R15", "R2", "T1", "T2", "HOLD", "NOSTOP", "DRIFT")


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



class PBExits(QCAlgorithm):

    def initialize(self):
        self.set_start_date(*START)
        self.set_end_date(*END)
        self.set_cash(1_000_000)
        self.f = self.add_future(Futures.Indices.NASDAQ_100_E_MINI, Resolution.MINUTE, fill_forward=False,
                                 data_normalization_mode=DataNormalizationMode.RAW,
                                 data_mapping_mode=DataMappingMode.OPEN_INTEREST,
                                 contract_depth_offset=0, extended_market_hours=True)
        self.f.set_filter(0, 180)
        self.adx = ADX(14)
        self.hh = deque(maxlen=20)
        self.ll = deque(maxlen=20)
        self.trades = {e: [] for e in EXITS}     # (pts, risk, r, usd, era, year, date)
        self.pos = {}
        self.date = None
        self.mapped = None
        self.cal = []
        self._new_day()

    def _new_day(self):
        self.pv = self.vv = 0.0
        self.orh = None
        self.active = self.touched = self.ready = False
        self.pblow = None
        self.pending = None
        self.signal_done = False
        self.drift_pending = False
        self.drift_done = False

    def _book(self, e, px, t):
        p = self.pos.pop(e)
        pts = px - p["e"]
        net = pts - COST / PV
        risk = p["risk"]
        self.trades[e].append((pts, risk, net / risk, net * PRICE / p["e"] * PV, era_of(t.year), t.year, t.date()))

    def on_data(self, data: Slice):
        bar = data.bars.get(self.f.symbol)
        if bar is None:
            return
        t = self.time
        m = t.hour * 60 + t.minute
        o, h, l, c, v = float(bar.open), float(bar.high), float(bar.low), float(bar.close), float(bar.volume)
        self.adx.update(h, l, c)
        if 9 * 60 + 30 < m <= 16 * 60 and self.date != t.date():
            for e in list(self.pos):
                self._book(e, o, t)
            self.date = t.date()
            self.mapped = self.f.mapped
            self._new_day()
            if t.date() >= date(*RECENT):
                self.cal.append(t.date())
        self.hh.append(h)
        self.ll.append(l)
        if self.date != t.date() or not (9 * 60 + 30 < m <= 16 * 60):
            return
        if self.f.mapped != self.mapped:
            for e in list(self.pos):
                self._book(e, c, t)
            self.signal_done = self.drift_done = True
            self.pending = None
            self.drift_pending = False
            self.mapped = self.f.mapped
        tex = 15 * 60 + 55
        # entries at this minute's open
        if self.pending is not None:
            pd_ = self.pending
            self.pending = None
            e0 = o
            for ex in EXITS:
                if ex == "DRIFT":
                    continue
                if ex in ("T1", "T2"):
                    sl = pd_["pbl"] - 0.25
                elif ex == "NOSTOP":
                    sl = None
                else:
                    sl = pd_["l20"]
                if sl is not None and sl >= e0:
                    continue
                risk = (e0 - sl) if sl is not None else max(1.0, e0 - pd_["l20"])
                tp = None
                if ex == "LIT":
                    tp = pd_["h5"]
                    if tp <= e0:
                        continue
                elif ex in ("R1", "T1"):
                    tp = e0 + risk
                elif ex == "R15":
                    tp = e0 + 1.5 * risk
                elif ex in ("R2", "T2"):
                    tp = e0 + 2 * risk
                self.pos[ex] = {"e": e0, "sl": sl, "tp": tp, "risk": risk}
        if self.drift_pending:
            self.drift_pending = False
            self.pos["DRIFT"] = {"e": o, "sl": None, "tp": None, "risk": max(1.0, 0.002 * o)}
        # exits
        for ex in list(self.pos):
            p = self.pos[ex]
            if p["sl"] is not None and l <= p["sl"]:
                self._book(ex, min(p["sl"], o), t)
            elif p["tp"] is not None and h >= p["tp"]:
                self._book(ex, max(p["tp"], o), t)
            elif m >= tex:
                self._book(ex, c, t)
        # VWAP / OR
        self.pv += (h + l + c) / 3.0 * v
        self.vv += v
        if m <= 10 * 60:
            self.orh = h if self.orh is None else max(self.orh, h)
            return
        if m == 11 * 60 + 30 and not self.drift_done:
            self.drift_pending = True
            self.drift_done = True
        if self.signal_done or m >= tex - 5 or self.vv <= 0:
            return
        vwap = self.pv / self.vv
        if not self.active:
            if c > self.orh:
                self.active = True
            return
        if l <= vwap:
            self.touched = True
            self.pblow = l if self.pblow is None else min(self.pblow, l)
        elif self.touched:
            self.pblow = min(self.pblow, l)
        if c < vwap:
            self.ready = False
            return
        if self.touched and c > vwap:
            self.ready = True
        if self.ready and self.adx.ready() and self.adx.prev is not None and self.adx.adx > 20 and self.adx.adx <= self.adx.prev:
            self.pending = {"h5": max(list(self.hh)[-5:]), "l20": min(self.ll), "pbl": self.pblow}
            self.signal_done = True

    def _summ(self, tr):
        n = len(tr)
        yrs = max(1.0, len(set(x[5] for x in tr)))
        usd = [x[3] for x in tr]
        mu = sum(usd) / n
        sd = math.sqrt(sum((x - mu) ** 2 for x in usd) / (n - 1)) if n > 1 else 0
        era = " ".join(f"{sum(x[3] for x in tr if x[4] == i) / max(1, sum(1 for x in tr if x[4] == i)):+.0f}" for i in range(len(ERAS)))
        rs = sorted(x[1] for x in tr)
        return (f"{n / yrs:.0f}/y win {sum(1 for x in tr if x[0] > 0) / n * 100:.0f}% gross {sum(x[0] for x in tr) / n:+.2f}pt "
                f"{sum(x[2] for x in tr) / n:+.3f}R ${mu:+.0f}/tr t{(mu / (sd / math.sqrt(n)) if sd > 0 else 0):+.1f} "
                f"risk med {rs[n // 2]:.1f}pt | $ by era {era}")

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
            pts, risk = day
            line = 100.0 if peak >= DD + 100.0 else peak - DD
            if scheme.startswith("FIX"):
                n = int(scheme[3:])
            else:
                n = int(float(scheme[4:]) / (risk * 2.0 + 2.5))
            n = max(1, min(20, n))
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

    def _evals(self, tr, schemes):
        byd = {x[6]: (x[0], x[1]) for x in tr if x[6] >= date(*RECENT)}
        cal = sorted(set(self.cal))
        seq = [byd.get(d) for d in cal]
        out = []
        for sc in schemes:
            res = [self._chain(seq, s0, sc) for s0 in range(0, max(0, len(seq) - 120))]
            ok = [r for r in res if r[2]]
            if not ok:
                out.append(f"{sc} 0%")
                continue
            out.append(f"{sc} {len(ok) / sum(r[1] for r in res) * 100:.0f}%/{sum(r[0] for r in ok) / len(ok):.0f}d/${sum(r[1] for r in res) / len(res) * 60:.0f}")
        return " | ".join(out)

    def on_end_of_algorithm(self):
        for e in list(self.pos):
            self._book(e, self.pos[e]["e"], self.time)
        for ex in EXITS:
            tr = self.trades[ex]
            if len(tr) < 10:
                continue
            self.set_runtime_statistic(f"P {ex}", self._summ(tr))
            rec = [x for x in tr if x[6] >= date(*RECENT)]
            sch = ("FIX1", "FIX2", "FIX4") if ex in ("NOSTOP", "DRIFT") else ("RISK150", "RISK300", "RISK500")
            if len(rec) >= 10:
                self.set_runtime_statistic(f"P {ex} 6y", f"{sum(x[2] for x in rec) / len(rec):+.3f}R win {sum(1 for x in rec if x[0] > 0) / len(rec) * 100:.0f}% | E25 " + self._evals(tr, sch))
