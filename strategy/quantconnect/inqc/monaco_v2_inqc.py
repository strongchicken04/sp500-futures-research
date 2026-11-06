# region imports
from AlgorithmImports import *
import math
from collections import deque
# endregion
#
# "MONACO" v2 - the stricter pullback version (owner 2026-11-06: "try what you
# think helps most", after v1 = plain EMA crosses = random walk minus costs).
# Idea: trade the pullback to the line only inside an ESTABLISHED intraday trend
# and in the direction our research found real (day direction / VWAP / NY).
# Computed INSIDE QuantConnect, aggregates only. Rules fixed before results.
#
# NQ front, 1-min bars, EMA200 of 1-min closes. SHORT setup (long mirror):
#   trend: >= 60 of the last 90 closes below the EMA and EMA < EMA 60 bars ago
#   touch: a bar whose high reaches the EMA while the trend holds -> armed, with
#          that bar's low as the trigger; armed for 10 bars; disarmed after 3
#          closes above the EMA
#   entry: first close below the armed bar's low (and below the EMA)
#   stop: 20-bar high + 1 tick (0.10%..0.80% from the entry, else skip)
#   target: 0.8 R or 1.5 R; one position at a time per variant; at most 2
#   entries per session (ASIA 18-02, LDN 02-08, PRE 08-09:30, NY 09:30-16:15);
#   flat 16:44 ET; no entries 16:15-18:00; costs 1.25 pt / MNQ; $550 risk.
# Variants: BASE; +VWAP (short only below the session VWAP from 18:00, long
#   above); +STRONG (EMA moved >= 0.15% over 60 bars in the trend direction);
#   NY (entries 09:45-15:30 only); ALL (VWAP + STRONG + NY).
# Verdict (fixed): a variant is a CANDIDATE only if mean net R > 0 with t >= 2
#   and positive in at least 7 of the 9 years 2018-2026.

START = (2018, 1, 1)
END = (2026, 12, 31)
VARS = ("BASE", "VWAP", "STRONG", "NY", "ALL")
RS = (0.8, 1.5)
L = 200
RISK, PV, COST = 550.0, 2.0, 1.25


def sess(m):
    if m > 18 * 60 or m <= 2 * 60:
        return "ASIA"
    if m <= 8 * 60:
        return "LDN"
    if m <= 9 * 60 + 30:
        return "PRE"
    return "NY"


class MonacoV2InQC(QCAlgorithm):

    def initialize(self):
        self.set_start_date(*START)
        self.set_end_date(*END)
        self.set_cash(1_000_000)
        self.nq = self.add_future(Futures.Indices.NASDAQ_100_E_MINI, Resolution.MINUTE, fill_forward=False,
                                  data_normalization_mode=DataNormalizationMode.RAW,
                                  data_mapping_mode=DataMappingMode.OPEN_INTEREST,
                                  contract_depth_offset=0, extended_market_hours=True)
        self.nq.set_filter(0, 180)
        self._reset()
        self.mapped = None
        self.pos = {}
        self.res = {}
        self.cnt = {}
        self.vw_pv = self.vw_v = 0.0
        self.vw_day = None

    def _reset(self):
        self.ema = None
        self.eh = deque(maxlen=61)
        self.side = deque(maxlen=90)
        self.hi = deque(maxlen=20)
        self.lo = deque(maxlen=20)
        self.arm = {1: None, -1: None}
        self.above = 0
        self.below = 0
        self.prevc = None

    def _close(self, key, tr, px, day):
        pts = (px - tr["e"]) * tr["d"] - COST
        self.res.setdefault(key, []).append((pts / tr["dist"], pts * PV * tr["n"], tr["s"], tr["y"], day))
        del self.pos[key]

    def on_data(self, data: Slice):
        bar = data.bars.get(self.nq.symbol)
        if bar is None:
            return
        t = self.time
        m = t.hour * 60 + t.minute
        day = (t + timedelta(hours=6)).date()
        o, h, l, c, v = float(bar.open), float(bar.high), float(bar.low), float(bar.close), float(bar.volume)
        if self.mapped is not None and self.nq.mapped != self.mapped:
            for key, tr in list(self.pos.items()):
                self._close(key, tr, self.prevc if self.prevc else c, day)
            self._reset()
        self.mapped = self.nq.mapped
        if self.vw_day != day:
            self.vw_day, self.vw_pv, self.vw_v = day, 0.0, 0.0
        self.vw_pv += (h + l + c) / 3.0 * v
        self.vw_v += v
        vwap = self.vw_pv / self.vw_v if self.vw_v > 0 else c
        for key, tr in list(self.pos.items()):
            if tr["d"] == -1:
                if h >= tr["sl"]:
                    self._close(key, tr, max(tr["sl"], o), day)
                elif l <= tr["tp"]:
                    self._close(key, tr, o if o < tr["tp"] else tr["tp"], day)
            else:
                if l <= tr["sl"]:
                    self._close(key, tr, min(tr["sl"], o), day)
                elif h >= tr["tp"]:
                    self._close(key, tr, o if o > tr["tp"] else tr["tp"], day)
        if 16 * 60 + 44 <= m < 18 * 60:
            for key, tr in list(self.pos.items()):
                self._close(key, tr, c, day)
        e = c if self.ema is None else self.ema + (c - self.ema) * 2.0 / (L + 1)
        self.ema = e
        self.eh.append(e)
        self.side.append(1 if c > e else -1)
        self.hi.append(h)
        self.lo.append(l)
        self.above = self.above + 1 if c > e else 0
        self.below = self.below + 1 if c < e else 0
        if len(self.eh) < 61 or len(self.side) < 90 or len(self.hi) < 20:
            self.prevc = c
            return
        e60 = self.eh[0]
        nb = sum(1 for s in self.side if s == -1)
        trend = {-1: nb >= 60 and e < e60, 1: (90 - nb) >= 60 and e > e60}
        strong = {-1: (e60 - e) / e >= 0.0015, 1: (e - e60) / e >= 0.0015}
        # arming / disarming
        for d in (-1, 1):
            a = self.arm[d]
            if a is not None:
                a["left"] -= 1
                if a["left"] <= 0 or (d == -1 and self.above >= 3) or (d == 1 and self.below >= 3):
                    self.arm[d] = None
            if trend[d] and ((d == -1 and h >= e) or (d == 1 and l <= e)):
                self.arm[d] = {"lvl": l if d == -1 else h, "left": 10}
        can = not (16 * 60 + 15 <= m <= 18 * 60)
        if can:
            for d in (-1, 1):
                a = self.arm[d]
                if a is None or a["left"] == 10:            # not on the touch bar itself
                    continue
                if not ((d == -1 and c < a["lvl"] and c < e) or (d == 1 and c > a["lvl"] and c > e)):
                    continue
                self.arm[d] = None
                sl = (max(self.hi) + 0.25) if d == -1 else (min(self.lo) - 0.25)
                dist = max(abs(sl - c), c * 0.0010)
                if dist > c * 0.0080:
                    continue
                n = max(1, int(RISK / (dist * PV)))
                s = sess(m)
                vw_ok = (c < vwap) if d == -1 else (c > vwap)
                ny_ok = 9 * 60 + 45 <= m <= 15 * 60 + 30
                for V in VARS:
                    if V == "VWAP" and not vw_ok:
                        continue
                    if V == "STRONG" and not strong[d]:
                        continue
                    if V == "NY" and not ny_ok:
                        continue
                    if V == "ALL" and not (vw_ok and strong[d] and ny_ok):
                        continue
                    ck = (V, day, s)
                    if self.cnt.get(ck, 0) >= 2:
                        continue
                    for R in RS:
                        key = (V, R)
                        if key in self.pos:
                            continue
                        self.pos[key] = {"d": d, "e": c, "sl": c - d * dist, "tp": c + d * dist * R, "dist": dist,
                                         "n": n, "s": s, "y": t.year}
                    self.cnt[ck] = self.cnt.get(ck, 0) + 1
        self.prevc = c

    def _lucid(self, trades):
        days = {}
        for rnet, usd, s, y, d in trades:
            days.setdefault(d, []).append(usd)
        seq = [days[d] for d in sorted(days)]
        res = []
        for s0 in range(0, max(0, len(seq) - 60), 5):
            i, ev, eq, peak, best, td, ok = s0, 1, 0.0, 0.0, 0.0, 0, False
            while i < len(seq) and i - s0 < 250:
                line = 100.0 if peak >= 2100.0 else peak - 2000.0
                run, mn = eq, eq
                for u in seq[i]:
                    run += u
                    mn = min(mn, run)
                i += 1
                if mn <= line:
                    ev += 1
                    eq = peak = best = 0.0
                    td = 0
                    continue
                best = max(best, run - eq)
                eq = run
                td += 1
                peak = max(peak, eq)
                if eq >= 3000.0 and best <= 0.5 * eq and td >= 2:
                    ok = True
                    break
            if ok:
                res.append((i - s0, ev))
        if not res:
            return "no pass"
        return f"pass/att {len(res) / sum(x[1] for x in res) * 100:.0f}% {sum(x[0] for x in res) / len(res):.0f} trading-day seq ${sum(x[1] for x in res) / len(res) * 90:.0f}"

    def on_end_of_algorithm(self):
        yrs = max(1.0, (self.time - datetime(*START)).days / 365.25)
        for key in sorted(self.res):
            tr = self.res[key]
            r = [x[0] for x in tr]
            n = len(r)
            if n < 20:
                continue
            mu = sum(r) / n
            sd = math.sqrt(sum((x - mu) ** 2 for x in r) / (n - 1))
            win = sum(1 for x in r if x > 0) / n * 100
            gp = sum(x for x in r if x > 0)
            gl = -sum(x for x in r if x < 0)
            ss = " ".join(f"{s} {sum(x[0] for x in tr if x[2] == s) / max(1, sum(1 for x in tr if x[2] == s)):+.3f}/{sum(1 for x in tr if x[2] == s)}"
                          for s in ("ASIA", "LDN", "PRE", "NY") if any(x[2] == s for x in tr))
            V, R = key
            self.set_runtime_statistic(f"M2 {V} {R}R", f"{n / yrs:.0f}/y win {win:.1f}% {mu:+.3f}R t{mu / (sd / math.sqrt(n)):+.1f} PF {gp / gl if gl else 0:.2f} "
                                       f"${sum(x[1] for x in tr) / yrs:+,.0f}/y | {ss}")
            by = []
            pos_years = 0
            for y in sorted(set(x[3] for x in tr)):
                ry = [x[0] for x in tr if x[3] == y]
                my = sum(ry) / len(ry)
                pos_years += my > 0
                by.append(f"{y % 100}:{my:+.2f}")
            self.set_runtime_statistic(f"M2 years {V} {R}R", f"+{pos_years}/{len(by)} " + " ".join(by))
            if R == 0.8 or V == "ALL":
                self.set_runtime_statistic(f"M2 eval {V} {R}R", self._lucid(tr))
