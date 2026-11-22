# region imports
from AlgorithmImports import *
import math
from collections import deque
# endregion
#
# NOISE AREA TREND FOLLOWER v2 - robustness + Lucid 25K (owner 2026-11-22: long + short trend follower).
# v1 (trend_follow_inqc.py): NA30 +$203 / trade per NQ, t 4.2, long +285 / short +126, all eras positive.
# FIXED BEFORE RESULTS, NQ minute 2010-2026 INSIDE QuantConnect, aggregates only:
#   sigma(m) = mean |close(m)/O - 1| over the last 14 days at minute m; UB = max(O, prevC) x (1 + k sigma),
#   LB = min(O, prevC) x (1 - k sigma); entries at the check marks (p > UB long, p < LB short), trailing exit
#   at the marks when p < max(UB, VWAP) (long) / p > min(LB, VWAP) (short); flat at 15:59; $15 per NQ trade.
#   BASE  k 1, marks every 30 min 10:00-15:30, fill at the mark close (= v1 NA30)
#   NX    BASE but every entry / exit fills at the NEXT minute's open (conservative)
#   K075 / K125  k = 0.75 / 1.25 (NX fills)
#   I15 / I60    marks every 15 min (10:00-15:45) / 60 min (10:00-15:00) (NX fills)
# Stats per variant ($ per NQ at today's price 28,530): trades / yr, win, $ / trade, t, $ / yr, max DD,
#   long / short $ / trade, eras, worst single trade (real $ per MNQ, last 6 years).
# Lucid 25K on REAL points, last 6 years (from 2020-11-20), all trades in order (closed-trade breach check),
#   MNQ $2 / pt + $2.50 per round trip: eval (+$1,250, $1,000 EOD trailing DD locking +$100 at $1,100, best
#   day <= 50%, fee $60) and funded (same DD, locked after the first payout, payout = min(50%, $1,000) when
#   5 days >= $100 and $1,000 is available, 90% kept, <= 500 days); sizes 1 / 2 / 3 MNQ; for BASE and NX.

START = (2010, 1, 1)
END = (2026, 12, 31)
PRICE, PV, COST = 28530.0, 20.0, 15.0
ERAS = ((2010, 2013), (2014, 2017), (2018, 2021), (2022, 2026))
RECENT = date(2020, 11, 20)
CFG = {"BASE": (1.0, 30, False), "NX": (1.0, 30, True), "K075": (0.75, 30, True), "K125": (1.25, 30, True),
       "I15": (1.0, 15, True), "I60": (1.0, 60, True)}


def era_of(y):
    for i, (a, b) in enumerate(ERAS):
        if a <= y <= b:
            return i
    return None


def marks(iv):
    last = 15 * 60 + (45 if iv == 15 else 30 if iv == 30 else 0)
    return set(range(10 * 60, last + 1, iv))


class V:
    def __init__(self, k, cfg):
        self.k = k
        self.mult, self.iv, self.nx = cfg
        self.marks = marks(self.iv)
        self.pos = None
        self.act = None          # pending action at the next open: ("enter", d) / ("exit",) / ("rev", d)
        self.trades = []         # (usd_scaled, dir, era, year, date, pts_real)


class NoiseAreaV2(QCAlgorithm):

    def initialize(self):
        self.set_start_date(*START)
        self.set_end_date(*END)
        self.set_cash(1_000_000)
        self.f = self.add_future(Futures.Indices.NASDAQ_100_E_MINI, Resolution.MINUTE, fill_forward=False,
                                 data_normalization_mode=DataNormalizationMode.RAW,
                                 data_mapping_mode=DataMappingMode.OPEN_INTEREST,
                                 contract_depth_offset=0, extended_market_hours=True)
        self.f.set_filter(0, 180)
        self.v = {k: V(k, c) for k, c in CFG.items()}
        self.hist = {}
        self.mapped = None
        self.day = None
        self.prevC = None
        self.cal = []
        self._new()

    def _new(self):
        self.O = None
        self.pv = self.vv = 0.0
        self.today = {}
        self.lastC = None
        self.bad = False

    def _book(self, v, px, t):
        p = v.pos
        pts = (px - p["e"]) * p["d"]
        v.trades.append((pts * PRICE / p["e"] * PV - COST, p["d"], era_of(t.year), t.year, t.date(), pts))
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
                v.act = None
                if v.pos is not None:
                    self._book(v, self.lastC if self.lastC else o, t)
            if self.day is not None and self.O is not None:
                if not self.bad:
                    for mm, x in self.today.items():
                        self.hist.setdefault(mm, deque(maxlen=14)).append(x)
                    self.prevC = self.lastC
                else:
                    self.prevC = None
            self.day = t.date()
            self._new()
            if t.date() >= RECENT:
                self.cal.append(t.date())
        if rolled:
            self.bad = True
            for v in self.v.values():
                v.act = None
                if v.pos is not None:
                    self._book(v, c, t)
        if self.O is None:
            self.O = o
        self.lastC = c
        self.pv += (h + l + c) / 3.0 * vol
        self.vv += vol
        vw = self.pv / self.vv if self.vv > 0 else c
        self.today[m] = abs(c / self.O - 1.0)
        # pending next-open actions
        for v in self.v.values():
            if v.act is None:
                continue
            a = v.act
            v.act = None
            if a[0] in ("exit", "rev") and v.pos is not None:
                self._book(v, o, t)
            if a[0] in ("enter", "rev") and v.pos is None and not self.bad:
                v.pos = {"d": a[1], "e": o}
        if self.bad or self.prevC is None:
            return
        hq = self.hist.get(m)
        if hq is None or len(hq) < 14:
            return
        s = sum(hq) / 14.0
        for v in self.v.values():
            ub = max(self.O, self.prevC) * (1 + v.mult * s)
            lb = min(self.O, self.prevC) * (1 - v.mult * s)
            if m >= 15 * 60 + 59:
                if v.pos is not None:
                    if v.nx and m < 16 * 60:
                        v.act = ("exit",)
                    else:
                        self._book(v, c, t)
                continue
            if m not in v.marks:
                continue
            exit_ = False
            if v.pos is not None:
                p = v.pos
                exit_ = (p["d"] == 1 and c < max(ub, vw)) or (p["d"] == -1 and c > min(lb, vw))
            flat_after = v.pos is None or exit_
            d = 1 if c > ub else (-1 if c < lb else 0)
            if not v.nx:
                if exit_:
                    self._book(v, c, t)
                if flat_after and d != 0:
                    v.pos = {"d": d, "e": c}
            else:
                if exit_ and d != 0:
                    v.act = ("rev", d)
                elif exit_:
                    v.act = ("exit",)
                elif v.pos is None and d != 0:
                    v.act = ("enter", d)

    # ---------------------------------------------------------------- Lucid
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
            rec = [x[5] for x in tr if x[4] >= RECENT]
            worst = min(rec) * 2.0 - 2.5 if rec else 0
            self.set_runtime_statistic(f"N2 {k}",
                f"{n / yrs:.0f}/y win {sum(1 for x in u if x > 0) / n * 100:.0f}% ${mu:+.0f}/tr t{mu / (sd / math.sqrt(n)):+.1f} ${sum(u) / yrs:+,.0f}/y DD ${mdd:,.0f}"
                f" | L {sum(lo) / max(1, len(lo)):+.0f} S {sum(sh) / max(1, len(sh)):+.0f} | era {era} | worst/MNQ ${worst:,.0f}")
            if k in ("BASE", "NX"):
                seq = self._days(tr)
                cells_e, cells_f = [], []
                for nm in (1, 2, 3):
                    res = [self._eval(seq, s0, nm) for s0 in range(0, max(1, len(seq) - 120))]
                    ok = [r for r in res if r[2]]
                    cells_e.append(f"{nm}MNQ " + (f"{len(ok) / sum(r[1] for r in res) * 100:.0f}%/{sum(r[0] for r in ok) / len(ok):.0f}d/${sum(r[1] for r in res) / len(res) * 60:.0f}" if ok else "0%"))
                    fr = [self._funded(seq, s0, nm) for s0 in range(0, max(1, len(seq) - 120), 3)]
                    kk = len(fr)
                    cells_f.append(f"{nm}MNQ ${sum(r[0] for r in fr) / kk:,.0f} pay {sum(1 for r in fr if r[1] > 0) / kk * 100:.0f}% life {sum(r[2] for r in fr) / kk:.0f}d")
                self.set_runtime_statistic(f"E25 {k}", " | ".join(cells_e))
                self.set_runtime_statistic(f"F25 {k}", " | ".join(cells_f))
