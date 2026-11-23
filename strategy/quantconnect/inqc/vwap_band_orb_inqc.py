# region imports
from AlgorithmImports import *
import math
# endregion
#
# VWAP 20 BPS BAND + 15-MIN ORB (owner 2026-11-23): VWAP and its +-20 bps bands start at 09:30; OR 09:30-09:45;
# entry on a 5-min close above the OR high AND above VWAP + 20 bps (long) / below the OR low AND below
# VWAP - 20 bps (short); TP / SL "optimise, but always 0.625" -> TP = 0.625 x SL. NQ minute 2010-2026 INSIDE
# QuantConnect, aggregates only. FIXED BEFORE RESULTS:
#   times in ET (09:30 ET = the NY open); VWAP = RTH typical-price VWAP from 09:30; bands = VWAP x (1 +- 0.002).
#   5-min closes 09:50..15:00 ET (bar-end clock); entry at that close; first signal of the day only; exits on
#   later minute bars (stop first if both in one minute, gaps at the open); flat 15:55 ET; $15 per NQ trade.
#   random-walk break-even win rate = 1 / 1.625 = 61.5% before costs.
#   SL grid (% of the entry price): 0.10 0.15 0.20 0.25 0.30 0.40 0.50; TP = 0.625 x SL.
#   Selection only on 2010-2019 (in-sample), check on 2020-2026 (out-of-sample).
#   Conditions: BOTH (owner), OR (OR break only, control), BAND (band only, control).
#   $ per NQ at today's price (28,530). Lucid 25K eval (BOTH only; real points, last 6 years): n MNQ =
#   floor($950 / (SL pt x $2 + $2.50)), 1..20; target +$1,250, $1,000 EOD trailing DD locking +$100 at $1,100,
#   best day <= 50%, fee $60.

START = (2010, 1, 1)
END = (2026, 12, 31)
PRICE, PV, COST = 28530.0, 20.0, 15.0
# v2 (owner 2026-11-23: "isn't 20 bps too small? try other bands - this can't work as a filter"): OR break +
# band, bands 20 / 30 / 40 / 50 / 75 / 100 bps and VWAP standard-deviation bands 1 / 1.5 / 2 sigma
# (volume-weighted stdev of the typical price around the RTH VWAP); SL 0.20 / 0.30 / 0.40 / 0.50%,
# TP = 0.625 x SL; Lucid 25K eval for SL 0.40%.
SLS = (0.20, 0.30, 0.40, 0.50)
CONDS = ("B20", "B30", "B40", "B50", "B75", "B100", "S1", "S1.5", "S2")
ERAS = ((2010, 2013), (2014, 2017), (2018, 2021), (2022, 2026))
RECENT = date(2020, 11, 20)


def era_of(y):
    for i, (a, b) in enumerate(ERAS):
        if a <= y <= b:
            return i
    return None


class V:
    def __init__(self, k):
        self.k = k
        self.pos = None
        self.done = False
        self.trades = []          # (usd_scaled, dir, era, year, date, pts_real, sl_pts_real)


class VwapBandORB(QCAlgorithm):

    def initialize(self):
        self.set_start_date(*START)
        self.set_end_date(*END)
        self.set_cash(1_000_000)
        self.f = self.add_future(Futures.Indices.NASDAQ_100_E_MINI, Resolution.MINUTE, fill_forward=False,
                                 data_normalization_mode=DataNormalizationMode.RAW,
                                 data_mapping_mode=DataMappingMode.OPEN_INTEREST,
                                 contract_depth_offset=0, extended_market_hours=True)
        self.f.set_filter(0, 180)
        self.v = {(c, s): V((c, s)) for c in CONDS for s in SLS}
        self.mapped = None
        self.day = None
        self.cal = []
        self._new()

    def _new(self):
        self.pv = self.vv = self.pvv = 0.0
        self.orh = self.orl = None
        self.bad = False

    def _book(self, v, px, t):
        p = v.pos
        pts = (px - p["e"]) * p["d"]
        v.trades.append((pts * PRICE / p["e"] * PV - COST, p["d"], era_of(t.year), t.year, t.date(), pts, p["sld"]))
        v.pos = None

    def on_data(self, data: Slice):
        bar = data.bars.get(self.f.symbol)
        if bar is None:
            return
        t = self.time
        m = t.hour * 60 + t.minute
        o, h, l, c, vol = float(bar.open), float(bar.high), float(bar.low), float(bar.close), float(bar.volume)
        rolled = self.mapped is not None and self.f.mapped != self.mapped
        self.mapped = self.f.mapped
        if not (9 * 60 + 30 < m <= 16 * 60):
            return
        if self.day != t.date():
            for v in self.v.values():
                if v.pos is not None:
                    self._book(v, o, t)
                v.done = False
            self.day = t.date()
            self._new()
            if t.date() >= RECENT:
                self.cal.append(t.date())
        if rolled:
            self.bad = True
            for v in self.v.values():
                if v.pos is not None:
                    self._book(v, c, t)
                v.done = True
        tp_ = (h + l + c) / 3.0
        self.pv += tp_ * vol
        self.pvv += tp_ * tp_ * vol
        self.vv += vol
        vw = self.pv / self.vv if self.vv > 0 else c
        vsd = math.sqrt(max(0.0, self.pvv / self.vv - vw * vw)) if self.vv > 0 else 0.0
        if m <= 9 * 60 + 45:
            self.orh = h if self.orh is None else max(self.orh, h)
            self.orl = l if self.orl is None else min(self.orl, l)
        # exits
        for v in self.v.values():
            p = v.pos
            if p is None:
                continue
            if p["d"] == 1:
                if l <= p["sl"]:
                    self._book(v, min(p["sl"], o), t)
                elif h >= p["tp"]:
                    self._book(v, max(p["tp"], o), t)
            else:
                if h >= p["sl"]:
                    self._book(v, max(p["sl"], o), t)
                elif l <= p["tp"]:
                    self._book(v, min(p["tp"], o), t)
            if v.pos is not None and m >= 15 * 60 + 55:
                self._book(v, c, t)
        if self.bad or m % 5 != 0 or not (9 * 60 + 50 <= m <= 15 * 60) or self.orh is None:
            return
        sig = {}
        for cond in CONDS:
            w = (vw * float(cond[1:]) / 10000.0) if cond.startswith("B") else float(cond[1:]) * vsd
            sig[cond] = 1 if (c > self.orh and c > vw + w) else (-1 if (c < self.orl and c < vw - w) else 0)
        for (cond, slp), v in self.v.items():
            if v.done or v.pos is not None:
                continue
            d = sig[cond]
            if d == 0:
                continue
            sld = c * slp / 100.0
            v.pos = {"d": d, "e": c, "sl": c - d * sld, "tp": c + d * 0.625 * sld, "sld": sld}
            v.done = True

    def _eval(self, seq, s0):
        i, ev = s0, 1
        bal = peak = best = 0.0
        td = 0
        while i < len(seq) and i - s0 < 250:
            day = seq[i]
            i += 1
            if day is None:
                continue
            pts, sld = day
            n = max(1, min(20, int(950.0 / (sld * 2.0 + 2.5))))
            line = 100.0 if peak >= 1100.0 else peak - 1000.0
            run = bal + pts * 2.0 * n - 2.5 * n
            if run <= line:
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

    def on_end_of_algorithm(self):
        def st(tr):
            n = len(tr)
            if n < 10:
                return "n<10", 0.0
            u = [x[0] for x in tr]
            mu = sum(u) / n
            sd = math.sqrt(sum((x - mu) ** 2 for x in u) / (n - 1))
            return f"${mu:+.0f}/tr t{mu / (sd / math.sqrt(n)):+.1f}", mu
        for (cond, slp), v in self.v.items():
            tr = v.trades
            n = len(tr)
            if n < 20:
                continue
            yrs = max(1.0, len(set(x[3] for x in tr)))
            u = [x[0] for x in tr]
            win = sum(1 for x in u if x > 0) / n * 100
            allst, _ = st(tr)
            ins, _ = st([x for x in tr if x[3] <= 2019])
            oos, _ = st([x for x in tr if x[3] >= 2020])
            lo = [x[0] for x in tr if x[1] == 1]
            sh = [x[0] for x in tr if x[1] == -1]
            era = " ".join(f"{sum(x[0] for x in tr if x[2] == i) / max(1, sum(1 for x in tr if x[2] == i)):+.0f}" for i in range(len(ERAS)))
            cum = pk = mdd = 0.0
            for x in u:
                cum += x
                pk = max(pk, cum)
                mdd = min(mdd, cum - pk)
            self.set_runtime_statistic(f"VB {cond} SL{slp:.2f}%",
                f"{n / yrs:.0f}/y win {win:.0f}% {allst} ${sum(u) / yrs:+,.0f}/y DD ${mdd:,.0f} | IS10-19 {ins} | OOS20-26 {oos} | L {sum(lo) / max(1, len(lo)):+.0f} S {sum(sh) / max(1, len(sh)):+.0f} | era {era}")
            if slp == 0.40:
                byd = {x[4]: (x[5], x[6]) for x in tr if x[4] >= RECENT}
                seq = [byd.get(d) for d in sorted(set(self.cal))]
                res = [self._eval(seq, s0) for s0 in range(0, max(1, len(seq) - 120))]
                ok = [r for r in res if r[2]]
                rec = [x for x in tr if x[4] >= RECENT]
                nm = sorted(max(1, min(20, int(950.0 / (x[6] * 2.0 + 2.5)))) for x in rec)
                self.set_runtime_statistic(f"VB25 {cond} SL{slp:.2f}%",
                    (f"eval {len(ok) / sum(r[1] for r in res) * 100:.0f}%/{sum(r[0] for r in ok) / len(ok):.0f}d/${sum(r[1] for r in res) / len(res) * 60:.0f}" if ok else "eval 0%")
                    + f" | MNQ median {nm[len(nm) // 2] if nm else 0} | last6y win {sum(1 for x in rec if x[5] > 0) / max(1, len(rec)) * 100:.0f}% {len(rec) / 6:.0f}/y")
