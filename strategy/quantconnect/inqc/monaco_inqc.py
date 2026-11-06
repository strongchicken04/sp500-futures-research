# region imports
from AlgorithmImports import *
import math
from collections import deque
# endregion
#
# "MONACO v2" RECONSTRUCTION (owner screenshots 2026-11-06: MNQ 30 s / 1 min,
# one slow line, short / long when price comes back across it, stop beyond the
# last swing, target 0.8-0.9 R, size = fixed $ risk / stop). The real code is
# unknown; this tests the reconstruction. Computed INSIDE QuantConnect, only
# aggregates are returned. Rules fixed before results.
#
# NQ front contract, 1-minute bars, all sessions. Line = EMA(L) of 1-min closes,
# L = 100 / 200 / 300. Signal: SHORT when a bar closes below the EMA after the
# previous bar closed at / above it (LONG mirror). Filter NONE, or SLOPE (short
# only while the EMA is lower than 30 bars ago, long mirror). Stop = highest
# high (short) / lowest low (long) of the last 20 bars + 1 tick, at least 0.10%
# from the entry; skip the signal if the stop is > 0.80% away. Target = R x the
# stop distance, R = 0.6 / 0.8 / 1.0 / 1.5. Entry at the signal bar's close;
# from the next bar stop / target on bar high / low, stop first if both in one
# bar; one position at a time per variant; flat at 16:44 ET (the daily break /
# prop rule), no entries 16:15-18:00. Costs 1.25 points per MNQ round trip
# ($2.50: fees + 1 tick). Size = floor($550 / (stop points x $2)) MNQ (>= 1).
# Metrics: trades a year, win %, mean net R, t, profit factor, by entry
# session (ASIA 18-02, LDN 02-08, PRE 08-09:30, NY 09:30-16:15), by year for
# the main variant (EMA200, NONE, 0.8 R); Lucid 50K evaluation from the $
# results (target +$3,000, $2,000 EOD trailing drawdown locking at +$100,
# intraday low of the running day P&L after each closed trade counts, best day
# <= 50% of profit, fee $90; starts every 5th trading day).
# Break-even win rate for a target of R: 1 / (1 + R) before costs (0.8 R: 55.6%).

START = (2018, 1, 1)
END = (2026, 12, 31)
LS = (100, 200, 300)
FILTERS = ("NONE", "SLOPE")
RS = (0.6, 0.8, 1.0, 1.5)
RISK, PV, COST = 550.0, 2.0, 1.25


def sess(m):
    if m > 18 * 60 or m <= 2 * 60:
        return "ASIA"
    if m <= 8 * 60:
        return "LDN"
    if m <= 9 * 60 + 30:
        return "PRE"
    return "NY"


class MonacoInQC(QCAlgorithm):

    def initialize(self):
        self.set_start_date(*START)
        self.set_end_date(*END)
        self.set_cash(1_000_000)
        self.nq = self.add_future(Futures.Indices.NASDAQ_100_E_MINI, Resolution.MINUTE, fill_forward=False,
                                  data_normalization_mode=DataNormalizationMode.RAW,
                                  data_mapping_mode=DataMappingMode.OPEN_INTEREST,
                                  contract_depth_offset=0, extended_market_hours=True)
        self.nq.set_filter(0, 180)
        self.ema = {L: None for L in LS}
        self.hist = {L: deque(maxlen=31) for L in LS}
        self.hi = deque(maxlen=20)
        self.lo = deque(maxlen=20)
        self.prevc = None
        self.prevema = {L: None for L in LS}
        self.mapped = None
        self.pos = {}                               # (L, F, R) -> open trade
        self.res = {}                               # (L, F, R) -> list of (R net, $ net, session, year, day)
        self.nbars = 0

    def _close(self, key, tr, px, day):
        d = tr["d"]
        pts = (px - tr["e"]) * d - COST
        rnet = pts / tr["dist"]
        usd = pts * PV * tr["n"]
        self.res.setdefault(key, []).append((rnet, usd, tr["s"], tr["y"], day))
        del self.pos[key]

    def on_data(self, data: Slice):
        bar = data.bars.get(self.nq.symbol)
        if bar is None:
            return
        t = self.time
        m = t.hour * 60 + t.minute
        day = (t + timedelta(hours=6)).date()
        o, h, l, c = float(bar.open), float(bar.high), float(bar.low), float(bar.close)
        if self.mapped is not None and self.nq.mapped != self.mapped:      # roll: flat everything, restart
            for key, tr in list(self.pos.items()):
                self._close(key, tr, self.prevc, day)
            self.ema = {L: None for L in LS}
            for L in LS:
                self.hist[L].clear()
            self.hi.clear(); self.lo.clear()
            self.prevc = None
        self.mapped = self.nq.mapped
        # exits on this bar
        for key, tr in list(self.pos.items()):
            if tr["d"] == -1:
                if h >= tr["sl"]:
                    self._close(key, tr, max(tr["sl"], o), day)
                elif l <= tr["tp"]:
                    self._close(key, tr, min(tr["tp"], o) if o < tr["tp"] else tr["tp"], day)
            else:
                if l <= tr["sl"]:
                    self._close(key, tr, min(tr["sl"], o), day)
                elif h >= tr["tp"]:
                    self._close(key, tr, max(tr["tp"], o) if o > tr["tp"] else tr["tp"], day)
        if 16 * 60 + 44 <= m < 18 * 60:                   # first bar from 16:44 (minutes can be missing)
            for key, tr in list(self.pos.items()):
                self._close(key, tr, c, day)
        # indicators
        self.hi.append(h); self.lo.append(l)
        for L in LS:
            e = self.ema[L]
            self.prevema[L] = e
            self.ema[L] = c if e is None else e + (c - e) * 2.0 / (L + 1)
            self.hist[L].append(self.ema[L])
        self.nbars += 1
        can = not (16 * 60 + 15 <= m <= 18 * 60) and len(self.hi) == 20 and self.prevc is not None
        if can:
            for L in LS:
                e, pe = self.ema[L], self.prevema[L]
                if pe is None or len(self.hist[L]) < 31:
                    continue
                d = -1 if (c < e and self.prevc >= pe) else (1 if (c > e and self.prevc <= pe) else 0)
                if d == 0:
                    continue
                slope_ok = (self.hist[L][-1] < self.hist[L][0]) if d == -1 else (self.hist[L][-1] > self.hist[L][0])
                sl = (max(self.hi) + 0.25) if d == -1 else (min(self.lo) - 0.25)
                dist = abs(sl - c)
                dist = max(dist, c * 0.0010)
                if dist > c * 0.0080:
                    continue
                sl = c - d * dist
                n = max(1, int(RISK / (dist * PV)))
                for F in FILTERS:
                    if F == "SLOPE" and not slope_ok:
                        continue
                    for R in RS:
                        key = (L, F, R)
                        if key in self.pos:
                            continue
                        self.pos[key] = {"d": d, "e": c, "sl": sl, "tp": c + d * dist * R, "dist": dist, "n": n,
                                         "s": sess(m), "y": t.year}
        self.prevc = c

    def _lucid(self, trades):
        days = {}
        for rnet, usd, s, y, d in trades:
            days.setdefault(d, []).append(usd)
        seq = [days[d] for d in sorted(days)]
        T, DD = 3000.0, 2000.0
        res = []
        for s0 in range(0, max(0, len(seq) - 120), 5):
            i, ev, eq, peak, best, td = s0, 1, 0.0, 0.0, 0.0, 0
            ok = False
            while i < len(seq) and i - s0 < 250:
                line = 100.0 if peak >= DD + 100.0 else peak - DD
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
                if eq >= T and best <= 0.5 * eq and td >= 2:
                    ok = True
                    break
            if ok:
                res.append((i - s0, ev))
        if not res:
            return "no pass"
        return f"pass/att {len(res) / sum(x[1] for x in res) * 100:.0f}% {sum(x[0] for x in res) / len(res):.0f}d ${sum(x[1] for x in res) / len(res) * 90:.0f}"

    def on_end_of_algorithm(self):
        yrs = max(1.0, (self.time - datetime(*START)).days / 365.25)
        for key in sorted(self.res):
            tr = self.res[key]
            r = [x[0] for x in tr]
            n = len(r)
            if n < 30:
                continue
            mu = sum(r) / n
            sd = math.sqrt(sum((x - mu) ** 2 for x in r) / (n - 1))
            win = sum(1 for x in r if x > 0) / n * 100
            gp = sum(x for x in r if x > 0)
            gl = -sum(x for x in r if x < 0)
            usd = sum(x[1] for x in tr)
            ss = []
            for s in ("ASIA", "LDN", "PRE", "NY"):
                rs = [x[0] for x in tr if x[2] == s]
                if rs:
                    ss.append(f"{s} {sum(rs) / len(rs):+.3f}/{len(rs)}")
            L, F, R = key
            self.set_runtime_statistic(f"MO E{L} {F} {R}R",
                                       f"{n / yrs:.0f}/y win {win:.1f}% {mu:+.3f}R t{mu / (sd / math.sqrt(n)):+.1f} PF {gp / gl if gl else 0:.2f} ${usd / yrs:+,.0f}/y | " + " ".join(ss))
            if key in ((200, "NONE", 0.8), (100, "NONE", 0.8), (200, "SLOPE", 0.8), (200, "NONE", 1.0)):
                self.set_runtime_statistic(f"MO eval E{L} {F} {R}R", self._lucid(tr))
            if key == (200, "NONE", 0.8):
                by = []
                for y in sorted(set(x[3] for x in tr)):
                    ry = [x[0] for x in tr if x[3] == y]
                    by.append(f"{y % 100} {sum(ry) / len(ry):+.3f}/{sum(1 for x in ry if x > 0) / len(ry) * 100:.0f}%")
                self.set_runtime_statistic("MO years E200 NONE 0.8R", " ".join(by))
        self.set_runtime_statistic("MO bars", str(self.nbars))
