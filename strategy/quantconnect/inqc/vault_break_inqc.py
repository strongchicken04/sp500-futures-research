# region imports
from AlgorithmImports import *
import math
# endregion
#
# "VAULT BREAK" (owner rules 2026-11-11). Computed INSIDE QuantConnect on NQ
# minute bars 2010-2026, aggregates only. Rules (owner) + test details FIXED
# BEFORE RESULTS. Central Time = ET - 1 h.
#   Level = price at midnight CT (open of the 01:00 ET minute) + K x ATR15,
#     ATR15 = mean (high - low) of the last 15 sessions' window 00:00-17:00 CT
#     (= 01:00-18:00 ET; the market halts 17:00-18:00 ET), K = 0.30 (owner;
#     0.20 / 0.40 as a neighbourhood check).
#   VWAP anchored at midnight CT (01:00 ET), typical price x volume.
#   From 10:00 CT: any 30-min candle (CT clock, :00 / :30) that closes above the
#     level AND above the VWAP -> LONG 1 NQ at that close. Fixed TP $800 = 40 pt,
#     fixed SL $1,500 = 75 pt. Max 3 trades a day, one at a time, long only, flat
#     at 14:30 CT (15:30 ET). Last entry candle closes 14:00 CT.
#   START "C1000" = first candle is the one OPENING at 10:00 CT (main reading of
#     "vcetne te 10:00"); "C0930" = the candle closing at 10:00 CT also counts.
#   Exits on minute bars (stop first if both in one minute; gaps fill at the
#     open). Costs $15 per round trip (fees + 1 tick in, 1 tick out ~ 0.75 pt).
#   EXIT "PTS" = the literal 40 / 75 points (meaningful for recent prices);
#     "PCT" = the same distances as % of today's NQ (28,530): 0.140% / 0.263%,
#     so old years are comparable ($ results then shown at today's price).
#   Controls: DRIFT = long at the 10:00 CT candle close every day with the same
#     TP / SL (what plain upward drift gives); SHORT = the mirror rule (below
#     midnight - K x ATR and below VWAP), information only.
# Random-walk break-even win rate = 75 / (40 + 75) = 65.2% before costs.
# Lucid 50K evaluation from the $ sequence: +$3,000 target, $2,000 EOD trailing
#   drawdown locking at +$100, intraday low of the closed-trade running P&L
#   counts, best day <= 50% of the profit, fee $90; starts every 5th day.

START = (2010, 1, 1)
END = (2026, 12, 31)
PRICE = 28530.0
TP_PT, SL_PT, PV, COST = 40.0, 75.0, 20.0, 15.0
ERAS = (("10-13", 2010, 2013), ("14-17", 2014, 2017), ("18-21", 2018, 2021), ("22-26", 2022, 2026))
KS = (0.20, 0.30, 0.40)


def era_of(y):
    for i, (_, a, b) in enumerate(ERAS):
        if a <= y <= b:
            return i
    return None


class Run:
    def __init__(self, key):
        self.key = key
        self.pos = None
        self.n_today = 0
        self.trades = []            # (usd, date, year)


class VaultBreakInQC(QCAlgorithm):

    def initialize(self):
        self.set_start_date(*START)
        self.set_end_date(*END)
        self.set_cash(1_000_000)
        self.f = self.add_future(Futures.Indices.NASDAQ_100_E_MINI, Resolution.MINUTE, fill_forward=False,
                                 data_normalization_mode=DataNormalizationMode.RAW,
                                 data_mapping_mode=DataMappingMode.OPEN_INTEREST,
                                 contract_depth_offset=0, extended_market_hours=True)
        self.f.set_filter(0, 180)
        self.ranges = []                 # completed session ranges (01:00-18:00 ET)
        self.day = None
        self.mid = None
        self.hi = self.lo = None
        self.pv = self.vv = 0.0
        self.c30 = None                  # building 30-min candle [open, high, low, close]
        self.mapped = None
        self.runs = {}
        for k in KS:
            for start in ("C1000", "C0930"):
                for ex in ("PTS", "PCT"):
                    self.runs[("LONG", k, start, ex)] = Run(("LONG", k, start, ex))
        for ex in ("PTS", "PCT"):
            self.runs[("DRIFT", 0.0, "C1000", ex)] = Run(("DRIFT", 0.0, "C1000", ex))
            self.runs[("SHORT", 0.30, "C1000", ex)] = Run(("SHORT", 0.30, "C1000", ex))

    def _book(self, r, px, t):
        p = r.pos
        usd = (px - p["e"]) * p["d"] * PV * p["scale"] - COST
        r.trades.append((usd, t.date(), t.year))
        r.pos = None

    def on_data(self, data: Slice):
        bar = data.bars.get(self.f.symbol)
        if bar is None:
            return
        t = self.time
        m = t.hour * 60 + t.minute                         # ET, bar END
        o, h, l, c, v = float(bar.open), float(bar.high), float(bar.low), float(bar.close), float(bar.volume)
        # new trading day at midnight CT = the first bar ending after 01:00 ET
        if 60 < m <= 18 * 60 and self.day != t.date():
            if self.day is not None and self.hi is not None:
                self.ranges.append(self.hi - self.lo)
                if len(self.ranges) > 15:
                    self.ranges.pop(0)
            self.day = t.date()
            self.mid = o
            self.hi, self.lo = h, l
            self.pv = self.vv = 0.0
            self.c30 = None
            self.mapped = self.f.mapped
            for r in self.runs.values():
                r.n_today = 0
        if self.day != t.date() or not (60 < m <= 18 * 60):
            return
        if self.f.mapped != self.mapped:                    # roll inside the day: flat, stop for today
            for r in self.runs.values():
                if r.pos is not None:
                    self._book(r, c, t)
                r.n_today = 3
            self.mapped = self.f.mapped
        self.hi, self.lo = max(self.hi, h), min(self.lo, l)
        self.pv += (h + l + c) / 3.0 * v
        self.vv += v
        vwap = self.pv / self.vv if self.vv > 0 else c
        # exits
        for r in self.runs.values():
            p = r.pos
            if p is None:
                continue
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
            if r.pos is not None and m >= 15 * 60 + 30:
                self._book(r, c, t)
        # 30-min candle on the CT clock (= ET :00 / :30 boundaries too)
        a = self.c30
        self.c30 = [o, h, l, c] if a is None else [a[0], max(a[1], h), min(a[2], l), c]
        if m % 30 != 0:
            return
        cc = self.c30[3]
        self.c30 = None
        if len(self.ranges) < 15:
            return
        atr = sum(self.ranges) / 15.0
        # candle closes at m (ET). C1000: closes 11:30..15:00 ET; C0930 also 11:00 ET
        for key, r in self.runs.items():
            kind, k, start, ex = key
            first_close = 11 * 60 + 30 if start == "C1000" else 11 * 60
            if not (first_close <= m <= 15 * 60) or r.pos is not None or r.n_today >= 3:
                continue
            go = 0
            if kind == "LONG" and cc > self.mid + k * atr and cc > vwap:
                go = 1
            elif kind == "SHORT" and cc < self.mid - k * atr and cc < vwap:
                go = -1
            elif kind == "DRIFT" and m == first_close and r.n_today == 0:
                go = 1
            if go == 0:
                continue
            if ex == "PTS":
                tpd, sld, scale = TP_PT, SL_PT, 1.0
            else:                                           # same % distances as at today's price
                tpd, sld = cc * TP_PT / PRICE, cc * SL_PT / PRICE
                scale = PRICE / cc                          # $ at today's price
            r.pos = {"d": go, "e": cc, "tp": cc + go * tpd, "sl": cc - go * sld, "scale": scale}
            r.n_today += 1

    def _lucid(self, tr):
        days = {}
        for usd, d, y in tr:
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
        for key in sorted(self.runs, key=str):
            r = self.runs[key]
            tr = r.trades
            if len(tr) < 20:
                continue
            usd = [x[0] for x in tr]
            n = len(usd)
            yrs = max(1.0, len(set(x[2] for x in tr)))
            mu = sum(usd) / n
            sd = math.sqrt(sum((x - mu) ** 2 for x in usd) / (n - 1))
            win = sum(1 for x in usd if x > 0) / n * 100
            cum = peak = mdd = 0.0
            for x in usd:
                cum += x
                peak = max(peak, cum)
                mdd = min(mdd, cum - peak)
            days = {}
            for x in tr:
                days[x[1]] = days.get(x[1], 0.0) + x[0]
            per = [[x[0] for x in tr if era_of(x[2]) == i] for i in range(len(ERAS))]
            kind, k, start, ex = key
            lab = f"VB {kind} K{k:.2f} {start} {ex}"
            self.set_runtime_statistic(lab, f"{n / yrs:.0f}/y win {win:.1f}% ${mu:+.0f}/tr t{mu / (sd / math.sqrt(n)):+.1f} "
                                       f"${sum(usd) / yrs:+,.0f}/y maxDD ${mdd:,.0f} worst day ${min(days.values()):,.0f} | "
                                       + " ".join(f"{sum(p) / len(p):+.0f}" if p else "-" for p in per))
            if kind == "LONG" and k == 0.30 and start == "C1000":
                by = []
                for y in sorted(set(x[2] for x in tr)):
                    uy = [x[0] for x in tr if x[2] == y]
                    by.append(f"{y % 100}:{sum(uy):+.0f}")
                self.set_runtime_statistic(lab + " years $", " ".join(by))
                self.set_runtime_statistic(lab + " eval", self._lucid(tr))
