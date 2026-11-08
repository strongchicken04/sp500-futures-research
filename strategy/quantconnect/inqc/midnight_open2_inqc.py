# region imports
from AlgorithmImports import *
import math
# endregion
#
# CZECH MIDNIGHT OPEN, round 2 (after round 1 on NQ: no direction, no magnet,
# no bounce beyond the placebo). New angles, FIXED BEFORE RESULTS:
#   G1 WEEKLY OPEN (Sunday 18:00 open, ICT "weekly open"): side of each day's
#      16:00 close vs the weekly open -> return to Friday 16:00 (rest of week),
#      by weekday of the signal (Mon..Thu); placebo = the Monday 09:30 open.
#   G2 ASIA OPEN DRIVE: return 18:00 -> 18:30 and 18:00 -> 20:00 (sign, and the
#      top / bottom 20% by size within the era) -> rest of the overnight (to
#      09:30) and the RTH day (09:30 -> 16:00), FOLLOW.
#   G3 REOPEN GAP: O18 vs prior 16:00 close (the 16:00-18:00 move) -> overnight
#      18:00 -> 09:30 and RTH, FOLLOW; and |gap| >= 0.15%.
#   G4 RS SPRINT x O18 (NQ with ES): RS at 10:00 (NQ - ES return since the RTH
#      open > 0.15% and above VWAP, mirror) split by agreement with the side of
#      the 10:00 price vs O18; bracket +0.20 / -0.30 to 15:55, resolved win
#      minus 60% by era.
#   G5 MIDNIGHT HOLD: long or short from 18:00 to 09:30 / to 16:00 next day by
#      the side of the prior RTH close vs that day's O18 (does the prior day's
#      position vs its own midnight open carry over?).
# Same bar: all four eras with the same sign and |t| >= 3.

START = (2010, 1, 1)
END = (2026, 12, 31)
ERAS = (("10-13", 2010, 2013), ("14-17", 2014, 2017), ("18-21", 2018, 2021), ("22-26", 2022, 2026))


def era_of(y):
    for i, (_, a, b) in enumerate(ERAS):
        if a <= y <= b:
            return i
    return None


def tstat(v):
    n = len(v)
    if n < 3:
        return 0.0
    mu = sum(v) / n
    sd = math.sqrt(sum((x - mu) ** 2 for x in v) / (n - 1))
    return mu / (sd / math.sqrt(n)) if sd > 0 else 0.0


class MidnightOpen2InQC(QCAlgorithm):

    def initialize(self):
        self.set_start_date(*START)
        self.set_end_date(*END)
        self.set_cash(1_000_000)
        self.nq = self._add(Futures.Indices.NASDAQ_100_E_MINI)
        self.es = self._add(Futures.Indices.SP_500_E_MINI)
        self.s = {"o18": None, "d18": None, "p1830": None, "p2000": None, "map": None, "pdc": None, "pdc_o18": None,
                  "rth": [], "rday": None, "ropen": None, "es_open": None, "es_c": None, "vw": [0.0, 0.0], "wo": None,
                  "wo_map": None, "mon_open": None}
        self.days = []
        self.week = []          # per-day (date, close16, wo, mon_open)

    def _add(self, tk):
        f = self.add_future(tk, Resolution.MINUTE, fill_forward=False,
                            data_normalization_mode=DataNormalizationMode.RAW,
                            data_mapping_mode=DataMappingMode.OPEN_INTEREST,
                            contract_depth_offset=0, extended_market_hours=True)
        f.set_filter(0, 180)
        return f

    def on_data(self, data: Slice):
        t = self.time
        m = t.hour * 60 + t.minute
        S = self.s
        eb = data.bars.get(self.es.symbol)
        if eb is not None and 9 * 60 + 30 < m <= 16 * 60:
            if S.get("es_day") != t.date():
                S["es_day"] = t.date()
                S["es_open"] = float(eb.open)
            S["es_c"] = float(eb.close)
        bar = data.bars.get(self.nq.symbol)
        if bar is None:
            return
        o, h, l, c, v = float(bar.open), float(bar.high), float(bar.low), float(bar.close), float(bar.volume)
        if 18 * 60 < m <= 18 * 60 + 15 and S["d18"] != t.date():
            # a new session opens: record the prior day's carry-over signal first
            S["o18"], S["d18"], S["map"] = o, t.date(), self.nq.mapped
            S["p1830"] = S["p2000"] = None
            S["carry"] = None
            if S["pdc"] is not None and S["pdc_o18"] is not None:
                S["carry"] = (1 if S["pdc"] > S["pdc_o18"] else -1, o)
            if t.weekday() == 6:                      # Sunday open = weekly open
                S["wo"], S["wo_map"] = o, self.nq.mapped
                S["mon_open"] = None
        if S["o18"] is not None:
            if S["p1830"] is None and m >= 18 * 60 + 30 and m < 19 * 60:
                S["p1830"] = c
            if S["p2000"] is None and m >= 20 * 60 and m < 21 * 60:
                S["p2000"] = c
        if 9 * 60 + 30 < m <= 16 * 60:
            if S["rday"] != t.date():
                S["rday"] = t.date()
                S["rth"] = []
                S["ropen"] = o
                S["vw"] = [0.0, 0.0]
                if t.weekday() == 0 and S["mon_open"] is None:
                    S["mon_open"] = o
            S["rth"].append((h, l, c))
            S["vw"][0] += (h + l + c) / 3 * v
            S["vw"][1] += v
            if m == 10 * 60:
                S["rs10"] = None
                if S["es_open"] and S["es_c"]:
                    rs = (c / S["ropen"] - 1) - (S["es_c"] / S["es_open"] - 1)
                    vwap = S["vw"][0] / S["vw"][1] if S["vw"][1] > 0 else c
                    S["rs10"] = 1 if (rs > 0.0015 and c > vwap) else (-1 if (rs < -0.0015 and c < vwap) else 0)
                    S["i10"] = len(S["rth"]) - 1
            if m == 16 * 60:
                self._finish(t)

    def _finish(self, t):
        S = self.s
        b = S["rth"]
        if len(b) < 200 or S["o18"] is None or self.nq.mapped != S["map"] or (t.date() - S["d18"]).days > 4:
            S["pdc"], S["pdc_o18"] = (b[-1][2] if b else None), None
            return
        H = [x[0] for x in b]
        L = [x[1] for x in b]
        C = [x[2] for x in b]
        op, o18 = S["ropen"], S["o18"]
        d = {"y": t.year, "era": era_of(t.year), "date": t.date(), "wd": t.weekday()}
        d["on"] = op / o18 - 1                                 # overnight 18:00 -> 09:30
        d["rth"] = C[-1] / op - 1
        if S["p1830"]:
            d["a30"] = S["p1830"] / o18 - 1
            d["a30_rest"] = op / S["p1830"] - 1
        if S["p2000"]:
            d["a2h"] = S["p2000"] / o18 - 1
            d["a2h_rest"] = op / S["p2000"] - 1
        if S["pdc"]:
            d["gap"] = o18 / S["pdc"] - 1
        if S.get("carry"):
            d["carry"] = S["carry"][0]
        # G4 RS x O18
        rs = S.get("rs10")
        if rs and S.get("i10") is not None:
            i0 = S["i10"]
            e = C[i0]
            up = dn = None
            for i in range(i0 + 1, min(385, len(b))):
                if up is None and H[i] >= e * 1.002:
                    up = i
                if dn is None and L[i] <= e * 0.997:
                    dn = i
                if up is not None and dn is not None:
                    break
            tgt, stp = (up, dn) if rs == 1 else (dn, up)
            res = -1 if (stp is not None and (tgt is None or stp <= tgt)) else (1 if tgt is not None else 0)
            side18 = 1 if e > o18 else -1
            d["rs"] = (res, rs == side18)
        # G1 weekly bookkeeping
        if S["wo"] is not None and self.nq.mapped == S["wo_map"]:
            self.week.append((t.date(), C[-1], S["wo"], S["mon_open"], t.weekday()))
        self.days.append(d)
        S["pdc"], S["pdc_o18"] = C[-1], o18
        S["rs10"] = None

    def on_end_of_algorithm(self):
        D = self.days

        def line(vals_by_era):
            allv = [x for v in vals_by_era for x in v]
            return " ".join(f"{sum(v) / len(v) * 1e4:+.1f}" if v else "-" for v in vals_by_era) + f" t{tstat(allv):+.1f} n{len(allv)}"

        def by_era(fn):
            per = [[] for _ in ERAS]
            for x in D:
                if x["era"] is None:
                    continue
                r = fn(x)
                if r is not None:
                    per[x["era"]].append(r)
            return per

        # G2 Asia open drive
        for k, rest in (("a30", "a30_rest"), ("a2h", "a2h_rest")):
            self.set_runtime_statistic(f"MN2 G2 {k} -> overnight", line(by_era(lambda x: (1 if x[k] > 0 else -1) * x[rest] if k in x and x[k] != 0 else None)))
            self.set_runtime_statistic(f"MN2 G2 {k} -> RTH", line(by_era(lambda x: (1 if x[k] > 0 else -1) * x["rth"] if k in x and x[k] != 0 else None)))
            vals = sorted(abs(x[k]) for x in D if k in x)
            if vals:
                cut = vals[int(len(vals) * 0.8)]
                self.set_runtime_statistic(f"MN2 G2 {k} big20 -> overnight", line(by_era(lambda x: (1 if x[k] > 0 else -1) * x[rest] if k in x and abs(x[k]) >= cut else None)))
                self.set_runtime_statistic(f"MN2 G2 {k} big20 -> RTH", line(by_era(lambda x: (1 if x[k] > 0 else -1) * x["rth"] if k in x and abs(x[k]) >= cut else None)))
        # G3 reopen gap
        self.set_runtime_statistic("MN2 G3 gap -> overnight", line(by_era(lambda x: (1 if x["gap"] > 0 else -1) * x["on"] if "gap" in x and x["gap"] != 0 else None)))
        self.set_runtime_statistic("MN2 G3 gap -> RTH", line(by_era(lambda x: (1 if x["gap"] > 0 else -1) * x["rth"] if "gap" in x and x["gap"] != 0 else None)))
        self.set_runtime_statistic("MN2 G3 gap>=.15% -> overnight", line(by_era(lambda x: (1 if x["gap"] > 0 else -1) * x["on"] if "gap" in x and abs(x["gap"]) >= 0.0015 else None)))
        self.set_runtime_statistic("MN2 G3 gap>=.15% -> RTH", line(by_era(lambda x: (1 if x["gap"] > 0 else -1) * x["rth"] if "gap" in x and abs(x["gap"]) >= 0.0015 else None)))
        # G5 carry-over
        self.set_runtime_statistic("MN2 G5 carry -> overnight", line(by_era(lambda x: x["carry"] * x["on"] if "carry" in x else None)))
        self.set_runtime_statistic("MN2 G5 carry -> RTH", line(by_era(lambda x: x["carry"] * x["rth"] if "carry" in x else None)))
        # G4 RS x O18
        for agree in (True, False):
            per = [[0, 0] for _ in ERAS]
            for x in D:
                if "rs" in x and x["rs"][1] == agree and x["rs"][0] != 0 and x["era"] is not None:
                    per[x["era"]][0] += x["rs"][0] == 1
                    per[x["era"]][1] += 1
            w = sum(p[0] for p in per)
            n = sum(p[1] for p in per)
            z = (w - 0.6 * n) / math.sqrt(n * 0.24) if n else 0
            self.set_runtime_statistic(f"MN2 G4 RS {'agree' if agree else 'against'} O18",
                                       " ".join(f"{(p[0] / p[1] - 0.6) * 100:+.1f}" if p[1] else "-" for p in per) + f" pp z{z:+.1f} n{n}")
        # G1 weekly open: rest-of-week return by weekday, side vs WO and vs Monday 09:30 (placebo)
        W = self.week
        fri = {}
        for dt_, c16, wo, mo, wd in W:
            key = dt_.isocalendar()[:2]
            if wd == 4:
                fri[key] = c16
        for lev in ("WO", "MON"):
            cells = []
            allv = []
            for wd in range(4):
                v = []
                for dt_, c16, wo, mo, w in W:
                    if w != wd:
                        continue
                    X = wo if lev == "WO" else mo
                    f = fri.get(dt_.isocalendar()[:2])
                    if X is None or f is None or c16 == X:
                        continue
                    v.append((1 if c16 > X else -1) * (f / c16 - 1))
                allv += v
                cells.append(f"{'MTWT'[wd]} {sum(v) / max(1, len(v)) * 1e4:+.1f} t{tstat(v):+.1f}")
            self.set_runtime_statistic(f"MN2 G1 {lev} side -> Fri", " ".join(cells) + f" | all t{tstat(allv):+.1f} n{len(allv)}")
        self.set_runtime_statistic("MN2 info", f"days {len(D)} week rows {len(W)}")
