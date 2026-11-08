# region imports
from AlgorithmImports import *
import math
# endregion
#
# CZECH MIDNIGHT OPEN (= 18:00 ET, the futures / Asia session open) - does it
# predict anything? (owner 2026-11-08: "test everything, all night, until you
# find something"). Computed INSIDE QuantConnect, aggregates only. Families and
# controls FIXED BEFORE RESULTS:
#   Levels: O18 = first minute open from 18:00 ET (Czech 00:00 all year: CET/ET
#   and CEST/EDT move together); O00 = the 00:00 ET open (ICT "midnight open");
#   PDC = prior 16:00 close; MIR = placebo: the 09:30 open mirrored around O18
#   (same distance, other side) - a level with no meaning.
#   RTH minute bars 09:30-16:00 of the same trading day; days whose contract
#   changed between 18:00 and 16:00 are skipped.
#   F1 direction: side = sign(price - level) at 09:30 open / 09:31 / 10:00 /
#      11:00; FOLLOW return (bp) from there to 12:00 and to 16:00, by era
#      2010-13 / 14-17 / 18-21 / 22-26, pooled t (FADE = minus).
#   F2 distance buckets of the 09:30 open from O18 (< 0.25%, 0.25-0.75%, >=
#      0.75%): FOLLOW to 16:00.
#   F3 magnet: share of days RTH trades back to the level (touch 09:31-15:59),
#      O18 vs MIR (placebo) vs O00 vs PDC, by distance bucket.
#   F4 first-touch reaction (09:35-15:00): signed return 15 / 30 / 60 min after
#      the touch, positive = back to the side it came from (bounce), for O18,
#      O00, PDC, MIR.
#   F5 sprints: side = FOLLOW / FADE of price vs O18 at 09:31 and 10:00,
#      brackets +0.20/-0.30 and +0.20/-0.40 to 15:55: resolved win minus the
#      random-walk rate (60.0 / 66.7%), by era, pooled z.
#   F6 Asia first hour: sign(19:00 - O18) -> return 19:00 -> 09:30 and RTH.
# v2: fewer than 390 RTH minutes on a day (missing minutes) - indices use the last bar.
# A finding needs the same sign in all four eras and |t| >= 3 (many tests),
# and must beat the placebo where one exists.

START = (2010, 1, 1)
END = (2026, 12, 31)
MARKET = "NQ"
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


class MidnightOpenInQC(QCAlgorithm):

    def initialize(self):
        self.set_start_date(*START)
        self.set_end_date(*END)
        self.set_cash(1_000_000)
        tk = {"NQ": Futures.Indices.NASDAQ_100_E_MINI, "ES": Futures.Indices.SP_500_E_MINI, "GC": Futures.Metals.GOLD}[MARKET]
        self.f = self.add_future(tk, Resolution.MINUTE, fill_forward=False,
                                 data_normalization_mode=DataNormalizationMode.RAW,
                                 data_mapping_mode=DataMappingMode.OPEN_INTEREST,
                                 contract_depth_offset=0, extended_market_hours=True)
        self.f.set_filter(0, 180)
        self.o18 = self.o00 = self.p19 = None
        self.map18 = None
        self.pdc = None
        self.rth = []
        self.rth_open = None
        self.rth_day = None
        self.days = []

    def on_data(self, data: Slice):
        bar = data.bars.get(self.f.symbol)
        if bar is None:
            return
        t = self.time
        m = t.hour * 60 + t.minute                        # bar END time
        o, h, l, c = float(bar.open), float(bar.high), float(bar.low), float(bar.close)
        if 18 * 60 < m <= 18 * 60 + 15 and (self.o18 is None or self.o18[1] != t.date()):
            self.o18 = (o, t.date())
            self.map18 = self.f.mapped
            self.o00 = None
            self.p19 = None
        if self.o18 is not None and self.p19 is None and m >= 19 * 60 and m < 20 * 60:
            self.p19 = c
        if 0 < m <= 15 and self.o00 is None and self.o18 is not None:
            self.o00 = o
        if 9 * 60 + 30 < m <= 16 * 60:
            if self.rth_day != t.date():
                self.rth_day = t.date()
                self.rth = []
                self.rth_open = o
                self.p0930 = c if self.p19 is None else None
                self.p_pre = self._last_c if hasattr(self, "_last_c") else None
            self.rth.append((h, l, c))
            if m == 16 * 60:
                self._finish(t)
        self._last_c = c

    def _finish(self, t):
        b = self.rth
        ok = len(b) >= 385 and self.o18 is not None and self.f.mapped == self.map18 and (t.date() - self.o18[1]).days <= 4
        if ok:
            o18 = self.o18[0]
            rec = {"y": t.year, "op": self.rth_open, "o18": o18, "o00": self.o00, "pdc": self.pdc,
                   "p19": self.p19, "pre": self.p_pre, "b": b}
            self.days.append(self._compute(rec))
        self.pdc = b[-1][2] if b else self.pdc
        self.rth = []

    def _compute(self, r):
        b, op, o18 = r["b"], r["op"], r["o18"]
        H = [x[0] for x in b]
        L = [x[1] for x in b]
        C = [x[2] for x in b]
        out = {"y": r["y"], "era": era_of(r["y"])}
        px = {"0930": op, "0931": C[0], "1000": C[29], "1100": C[89]}
        idx = {"0930": -1, "0931": 0, "1000": 29, "1100": 89}
        lev = {"O18": o18, "O00": r["o00"], "PDC": r["pdc"], "MIR": 2 * op - o18}
        out["dist"] = op / o18 - 1
        # F1 follow returns
        for ln in ("O18", "O00"):
            X = lev[ln]
            if X is None:
                continue
            for tk, p in px.items():
                s = 1 if p > X else (-1 if p < X else 0)
                if s == 0:
                    continue
                out[f"f1_{ln}_{tk}_16"] = s * (C[-1] / p - 1) * 1e4
                if idx[tk] < 149:
                    out[f"f1_{ln}_{tk}_12"] = s * (C[149] / p - 1) * 1e4
        # F3 magnet + F4 touch reaction
        for ln, X in lev.items():
            if X is None:
                continue
            side = 1 if op > X else -1
            first = None
            for i in range(0, len(b)):
                if L[i] <= X <= H[i]:
                    first = i
                    break
            out[f"t_{ln}"] = first is not None
            if first is not None and 5 <= first <= 330:
                for k in (15, 30, 60):
                    j = min(len(b) - 1, first + k)
                    out[f"r_{ln}_{k}"] = side * (C[j] / X - 1) * 1e4
        # F5 sprint brackets from 09:31 and 10:00 vs O18
        for tk in ("0931", "1000"):
            i0 = idx[tk]
            e = C[i0]
            s = 1 if e > o18 else (-1 if e < o18 else 0)
            if s == 0:
                continue
            fu = {}
            for lvl in (20, 30, 40):
                up = dn = None
                for i in range(i0 + 1, min(385, len(b))):
                    if up is None and H[i] >= e * (1 + lvl / 1e4):
                        up = i
                    if dn is None and L[i] <= e * (1 - lvl / 1e4):
                        dn = i
                    if up is not None and dn is not None:
                        break
                fu[lvl] = (up, dn)
            for side_name, d in (("FOL", s), ("FAD", -s)):
                for sp in (30, 40):
                    tgt = fu[20][0] if d == 1 else fu[20][1]
                    stp = fu[sp][1] if d == 1 else fu[sp][0]
                    if stp is not None and (tgt is None or stp <= tgt):
                        res = -1
                    elif tgt is not None:
                        res = 1
                    else:
                        res = 0
                    out[f"s_{tk}_{side_name}_{sp}"] = res
        # F6 Asia first hour
        if r["p19"] is not None:
            a = 1 if r["p19"] > o18 else -1
            out["a_on"] = a * (op / r["p19"] - 1) * 1e4
            out["a_rth"] = a * (C[-1] / op - 1) * 1e4
        return out

    def on_end_of_algorithm(self):
        D = self.days
        self.set_runtime_statistic(f"MN {MARKET} info", f"days {len(D)}")

        def era_line(key):
            per = [[] for _ in ERAS]
            allv = []
            for d in D:
                if key in d and d["era"] is not None:
                    per[d["era"]].append(d[key])
                    allv.append(d[key])
            cells = " ".join(f"{sum(v) / len(v):+.1f}" if v else "-" for v in per)
            return cells, tstat(allv), len(allv)

        for ln in ("O18", "O00"):
            for tk in ("0930", "0931", "1000", "1100"):
                c16, t16, n = era_line(f"f1_{ln}_{tk}_16")
                c12, t12, _ = era_line(f"f1_{ln}_{tk}_12")
                self.set_runtime_statistic(f"MN F1 {ln} {tk}", f"to16 {c16} t{t16:+.1f} | to12 {c12} t{t12:+.1f} n{n}")
        cells = []
        for lab, lo, hi in (("<.25", 0, 0.0025), (".25-.75", 0.0025, 0.0075), (">.75", 0.0075, 9)):
            v = [d["f1_O18_0930_16"] for d in D if "f1_O18_0930_16" in d and lo <= abs(d["dist"]) < hi]
            cells.append(f"{lab} {sum(v) / max(1, len(v)):+.1f}bp t{tstat(v):+.1f} n{len(v)}")
        self.set_runtime_statistic("MN F2 O18 dist follow16", " | ".join(cells))
        for lab, lo, hi in (("<.25", 0, 0.0025), (".25-.75", 0.0025, 0.0075), (">.75", 0.0075, 9)):
            sub = [d for d in D if lo <= abs(d["dist"]) < hi]
            cells = []
            for ln in ("O18", "MIR", "O00", "PDC"):
                v = [d[f"t_{ln}"] for d in sub if f"t_{ln}" in d]
                cells.append(f"{ln} {sum(v) / max(1, len(v)) * 100:.0f}%")
            self.set_runtime_statistic(f"MN F3 touch {lab}", " ".join(cells) + f" n{len(sub)}")
        for ln in ("O18", "O00", "PDC", "MIR"):
            parts = []
            for k in (15, 30, 60):
                cc, tt, n = era_line(f"r_{ln}_{k}")
                parts.append(f"+{k}m {cc} t{tt:+.1f}")
            self.set_runtime_statistic(f"MN F4 bounce {ln}", " | ".join(parts) + f" n{n}")
        for tk in ("0931", "1000"):
            for sn in ("FOL", "FAD"):
                for sp in (30, 40):
                    P = sp / (20 + sp)
                    per = [[0, 0] for _ in ERAS]
                    for d in D:
                        k = f"s_{tk}_{sn}_{sp}"
                        if k in d and d[k] != 0 and d["era"] is not None:
                            per[d["era"]][0] += d[k] == 1
                            per[d["era"]][1] += 1
                    w = sum(x[0] for x in per)
                    n = sum(x[1] for x in per)
                    z = (w - n * P) / math.sqrt(n * P * (1 - P)) if n else 0
                    cells = " ".join(f"{(x[0] / x[1] - P) * 100:+.1f}" if x[1] else "-" for x in per)
                    self.set_runtime_statistic(f"MN F5 {tk} {sn} 20/{sp}", f"{cells} pp z{z:+.1f} n{n}")
        c1, t1, n1 = era_line("a_on")
        c2, t2, n2 = era_line("a_rth")
        self.set_runtime_statistic("MN F6 asia1h", f"-> overnight {c1} t{t1:+.1f} | -> RTH {c2} t{t2:+.1f} n{n1}")
