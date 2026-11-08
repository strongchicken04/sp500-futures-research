# region imports
from AlgorithmImports import *
import math
# endregion
#
# CZECH MIDNIGHT OPEN, round 3 - angles with prior support (literature), FIXED
# BEFORE RESULTS:
#   H1 intraday momentum (Gao, Han, Li & Zhou 2018: the first half hour from
#      the prior close predicts the last half hour): sign of the return
#      O18 -> 10:00 (and, as the published version, prior 16:00 close ->
#      10:00) -> FOLLOW return 15:30 -> 16:00 and 15:00 -> 16:00.
#   H2 the day so far: sign of O18 -> 15:30 -> 15:30 -> 16:00 (and O18 -> 15:00
#      -> 15:00 -> 16:00), vs the same from the RTH open (09:30) as control.
#   H3 session chain: sign of Asia (18:00 -> 02:00) -> London (02:00 -> 08:00)
#      and -> RTH (09:30 -> 16:00); sign of London -> RTH; FOLLOW.
#   H4 volatility: |O18 -> 09:30| in the top fifth (cut per era) -> RTH range
#      (high - low) / open vs the other days (ratio), and |Asia| top fifth.
#   H5 Monday: F1-style follow from 10:00 to 16:00 by the side vs the Sunday
#      18:00 open, Mondays only, vs other days.
# Bar: all four eras the same sign and |t| >= 3 (direction); H4 is information.

START = (2010, 1, 1)
END = (2026, 12, 31)
MARKET = "ES"
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


class MidnightOpen3InQC(QCAlgorithm):

    def initialize(self):
        self.set_start_date(*START)
        self.set_end_date(*END)
        self.set_cash(1_000_000)
        tk = {"NQ": Futures.Indices.NASDAQ_100_E_MINI, "ES": Futures.Indices.SP_500_E_MINI}[MARKET]
        self.f = self.add_future(tk, Resolution.MINUTE, fill_forward=False,
                                 data_normalization_mode=DataNormalizationMode.RAW,
                                 data_mapping_mode=DataMappingMode.OPEN_INTEREST,
                                 contract_depth_offset=0, extended_market_hours=True)
        self.f.set_filter(0, 180)
        self.S = {"o18": None, "d18": None, "map": None, "p02": None, "p08": None, "pdc": None,
                  "rday": None, "rth": None}
        self.days = []

    def on_data(self, data: Slice):
        bar = data.bars.get(self.f.symbol)
        if bar is None:
            return
        t = self.time
        m = t.hour * 60 + t.minute
        S = self.S
        o, h, l, c = float(bar.open), float(bar.high), float(bar.low), float(bar.close)
        if 18 * 60 < m <= 18 * 60 + 15 and S["d18"] != t.date():
            S.update({"o18": o, "d18": t.date(), "map": self.f.mapped, "p02": None, "p08": None, "sun": t.weekday() == 6})
        if S["o18"] is not None:
            if S["p02"] is None and 2 * 60 <= m < 3 * 60:
                S["p02"] = c
            if S["p08"] is None and 8 * 60 <= m < 9 * 60:
                S["p08"] = c
        if 9 * 60 + 30 < m <= 16 * 60:
            if S["rday"] != t.date():
                S["rday"] = t.date()
                S["rth"] = {"op": o, "hi": h, "lo": l, "c1000": None, "c1500": None, "c1530": None}
            R = S["rth"]
            R["hi"] = max(R["hi"], h)
            R["lo"] = min(R["lo"], l)
            if m == 10 * 60:
                R["c1000"] = c
            if 15 * 60 <= m < 15 * 60 + 5 and R["c1500"] is None:
                R["c1500"] = c
            if 15 * 60 + 30 <= m < 15 * 60 + 35 and R["c1530"] is None:
                R["c1530"] = c
            if m == 16 * 60:
                self._finish(t, c)

    def _finish(self, t, c16):
        S = self.S
        R = S["rth"]
        ok = (S["o18"] is not None and self.f.mapped == S["map"] and (t.date() - S["d18"]).days <= 4
              and R["c1000"] and R["c1500"] and R["c1530"])
        if ok:
            o18, op = S["o18"], R["op"]
            d = {"y": t.year, "era": era_of(t.year), "mon": bool(S.get("sun"))}
            d["m18_10"] = R["c1000"] / o18 - 1
            if S["pdc"]:
                d["pdc_10"] = R["c1000"] / S["pdc"] - 1
            d["l30"] = c16 / R["c1530"] - 1
            d["l60"] = c16 / R["c1500"] - 1
            d["m18_1530"] = R["c1530"] / o18 - 1
            d["m18_1500"] = R["c1500"] / o18 - 1
            d["op_1530"] = R["c1530"] / op - 1
            d["op_1500"] = R["c1500"] / op - 1
            d["rth"] = c16 / op - 1
            d["r10_16"] = c16 / R["c1000"] - 1
            d["side10"] = 1 if R["c1000"] > o18 else -1
            d["on"] = op / o18 - 1
            d["rng"] = (R["hi"] - R["lo"]) / op
            if S["p02"]:
                d["asia"] = S["p02"] / o18 - 1
                if S["p08"]:
                    d["ldn"] = S["p08"] / S["p02"] - 1
            self.days.append(d)
        S["pdc"] = c16

    def on_end_of_algorithm(self):
        D = self.days

        def follow(sig, ret, cond=lambda x: True):
            per = [[] for _ in ERAS]
            for x in D:
                if x["era"] is None or sig not in x or ret not in x or x[sig] == 0 or not cond(x):
                    continue
                per[x["era"]].append((1 if x[sig] > 0 else -1) * x[ret])
            allv = [v for p in per for v in p]
            return " ".join(f"{sum(p) / len(p) * 1e4:+.2f}" if p else "-" for p in per) + f" t{tstat(allv):+.1f} n{len(allv)}"

        st = self.set_runtime_statistic
        st(f"MN3 {MARKET} info", f"days {len(D)}")
        st("MN3 H1 O18->10 => 15:30-16", follow("m18_10", "l30"))
        st("MN3 H1 O18->10 => 15-16", follow("m18_10", "l60"))
        st("MN3 H1 PDC->10 => 15:30-16 (Gao)", follow("pdc_10", "l30"))
        st("MN3 H1 PDC->10 => 15-16", follow("pdc_10", "l60"))
        st("MN3 H2 O18->15:30 => last30", follow("m18_1530", "l30"))
        st("MN3 H2 O18->15 => last60", follow("m18_1500", "l60"))
        st("MN3 H2 open->15:30 => last30 (ctl)", follow("op_1530", "l30"))
        st("MN3 H2 open->15 => last60 (ctl)", follow("op_1500", "l60"))
        st("MN3 H3 Asia => London", follow("asia", "ldn"))
        st("MN3 H3 Asia => RTH", follow("asia", "rth"))
        st("MN3 H3 London => RTH", follow("ldn", "rth"))
        st("MN3 H5 Mon side10 => 16", follow("side10", "r10_16", lambda x: x["mon"]))
        st("MN3 H5 other side10 => 16", follow("side10", "r10_16", lambda x: not x["mon"]))
        for k in ("on", "asia"):
            cells = []
            for i, (lab, a, b) in enumerate(ERAS):
                sub = [x for x in D if x["era"] == i and k in x]
                if len(sub) < 50:
                    cells.append(f"{lab} -")
                    continue
                cut = sorted(abs(x[k]) for x in sub)[int(len(sub) * 0.8)]
                big = [x["rng"] for x in sub if abs(x[k]) >= cut]
                rest = [x["rng"] for x in sub if abs(x[k]) < cut]
                cells.append(f"{lab} x{(sum(big) / len(big)) / (sum(rest) / len(rest)):.2f}")
            st(f"MN3 H4 |{k}| top20 -> RTH range ratio", " ".join(cells))
