# region imports
from AlgorithmImports import *
import math
from collections import deque
# endregion
#
# VAULT BREAK LONG + SHORT BY REGIME (owner 2026-11-24: "the eval can hardly be passed until we have a solid
# short trend follower" - market in a downtrend, Vault is long-only). NQ minute 2010-2026 INSIDE QuantConnect,
# aggregates only. FIXED BEFORE RESULTS:
#   LONG  = Vault Break as traded: level = midnight CT + K x ATR15, first 30-min close (candles opening 10:00 ..
#           13:30 CT) above the level AND the midnight VWAP -> long; SHORT = mirror: midnight - K x ATR15, close
#           below the level AND the VWAP -> short. TP 40 / SL 75 pt as the same % of today's NQ (0.140% /
#           0.263%, PCT), flat 14:30 CT, first signal of each side a day; K = 0.30 (0.20 / 0.40 for the short).
#   Regimes from the previous RTH close (16:00 ET): DN50 = below SMA50, DN200 = below SMA200, DN20 = 20-day
#   return < 0.
#   Stats per side / regime: trades / yr, win, $ per NQ trade (PCT), t, eras 2010-13 / 14-17 / 18-21 / 22-26,
#   last 6 years. Lucid 25K eval (last 6 years, 6 MNQ, first trade of the day only; target $1,250, $1,000 EOD
#   trailing DD locking +$100 at $1,100, best day <= 50%, fee $60): plans L (long only), LS50 / LS200 / LS20
#   (long in the up regime, short in the down regime), S50 (short only in DN50, nothing otherwise); pass per
#   attempt / trading days / fees, for all start days and for start days in the DN50 regime.

START = (2010, 1, 1)
END = (2026, 12, 31)
PRICE, PV, COST = 28530.0, 20.0, 15.0
TPP, SLP = 40.0 / 28530.0, 75.0 / 28530.0
ERAS = ((2010, 2013), (2014, 2017), (2018, 2021), (2022, 2026))
RECENT = date(2020, 11, 20)
KS = (0.20, 0.30, 0.40)


def era_of(y):
    for i, (a, b) in enumerate(ERAS):
        if a <= y <= b:
            return i
    return None


class VaultRegime(QCAlgorithm):

    def initialize(self):
        self.set_start_date(*START)
        self.set_end_date(*END)
        self.set_cash(1_000_000)
        self.f = self.add_future(Futures.Indices.NASDAQ_100_E_MINI, Resolution.MINUTE, fill_forward=False,
                                 data_normalization_mode=DataNormalizationMode.RAW,
                                 data_mapping_mode=DataMappingMode.OPEN_INTEREST,
                                 contract_depth_offset=0, extended_market_hours=True)
        self.f.set_filter(0, 180)
        self.ranges = []
        self.day = None
        self.mid = self.hi = self.lo = None
        self.pv = self.vv = 0.0
        self.c30 = None
        self.mapped = None
        self.closes = deque(maxlen=200)      # RTH 16:00 closes (raw; regime only)
        self.rth_last = None
        self.reg = {}
        self.cal = []
        self.pos = {}                         # (side, K) -> position
        self.done = {}
        self.trades = []                      # (side, K, pts_scaled, date, year, era, regime dict)

    def _book(self, key, px, t):
        p = self.pos.pop(key)
        pts = (px - p["e"]) * p["d"] * PRICE / p["e"]
        self.trades.append((key[0], key[1], pts, self.day, self.day.year, era_of(self.day.year), self.reg_today))

    def on_data(self, data: Slice):
        bar = data.bars.get(self.f.symbol)
        if bar is None:
            return
        t = self.time
        m = t.hour * 60 + t.minute
        o, h, l, c, v = float(bar.open), float(bar.high), float(bar.low), float(bar.close), float(bar.volume)
        if 9 * 60 + 30 < m <= 16 * 60:
            self.rth_last = c
        if 60 < m <= 18 * 60 and self.day != t.date():
            if self.day is not None and self.hi is not None:
                self.ranges.append(self.hi - self.lo)
                if len(self.ranges) > 15:
                    self.ranges.pop(0)
            if self.rth_last is not None and self.day is not None:
                self.closes.append(self.rth_last)
            self.day = t.date()
            if self.day >= RECENT:
                self.cal.append(self.day)
            cl = list(self.closes)
            self.reg_today = {
                "DN50": len(cl) >= 50 and cl[-1] < sum(cl[-50:]) / 50.0,
                "DN200": len(cl) >= 200 and cl[-1] < sum(cl) / 200.0,
                "DN20": len(cl) >= 21 and cl[-1] < cl[-21],
            }
            self.reg[self.day] = self.reg_today
            self.mid, self.hi, self.lo = o, h, l
            self.pv = self.vv = 0.0
            self.c30 = None
            self.mapped = self.f.mapped
            self.done = {}
        if self.day != t.date() or not (60 < m <= 18 * 60):
            return
        if self.f.mapped != self.mapped:
            for k in list(self.pos):
                self._book(k, c, t)
            self.done = {(s, k): True for s in ("L", "S") for k in KS}
            self.mapped = self.f.mapped
        self.hi, self.lo = max(self.hi, h), min(self.lo, l)
        self.pv += (h + l + c) / 3.0 * v
        self.vv += v
        vwap = self.pv / self.vv if self.vv > 0 else c
        for k in list(self.pos):
            p = self.pos[k]
            if p["d"] == 1:
                if l <= p["sl"]:
                    self._book(k, min(p["sl"], o), t)
                elif h >= p["tp"]:
                    self._book(k, max(p["tp"], o), t)
            else:
                if h >= p["sl"]:
                    self._book(k, max(p["sl"], o), t)
                elif l <= p["tp"]:
                    self._book(k, min(p["tp"], o), t)
            if k in self.pos and m >= 15 * 60 + 30:
                self._book(k, c, t)
        a = self.c30
        self.c30 = [o, h, l, c] if a is None else [a[0], max(a[1], h), min(a[2], l), c]
        if m % 30 != 0:
            return
        cc = self.c30[3]
        self.c30 = None
        if len(self.ranges) < 15 or not (11 * 60 + 30 <= m <= 15 * 60):
            return
        atr = sum(self.ranges) / 15.0
        for side in ("L", "S"):
            for k in KS:
                key = (side, k)
                if self.done.get(key) or key in self.pos:
                    continue
                if side == "L" and cc > self.mid + k * atr and cc > vwap:
                    d = 1
                elif side == "S" and cc < self.mid - k * atr and cc < vwap:
                    d = -1
                else:
                    continue
                self.pos[key] = {"d": d, "e": cc, "tp": cc * (1 + d * TPP), "sl": cc * (1 - d * SLP)}
                self.done[key] = True

    # ---------------------------------------------------------------- eval
    def _chain(self, seq, s0):
        i, ev = s0, 1
        bal = peak = best = 0.0
        td = 0
        n = 6
        while i < len(seq) and i - s0 < 250:
            pts = seq[i]
            i += 1
            if pts is None:
                continue
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
        for k in list(self.pos):
            self._book(k, self.pos[k]["e"], self.time)
        def st(tr):
            n = len(tr)
            if n < 15:
                return f"n {n}"
            yrs = max(1.0, len(set(x[4] for x in tr)))
            u = [x[2] * PV - COST for x in tr]
            mu = sum(u) / n
            sd = math.sqrt(sum((x - mu) ** 2 for x in u) / (n - 1))
            era = " ".join(f"{sum(x[2] * PV - COST for x in tr if x[5] == i) / max(1, sum(1 for x in tr if x[5] == i)):+.0f}" for i in range(len(ERAS)))
            rec = [x[2] * PV - COST for x in tr if x[3] >= RECENT]
            return (f"{n / yrs:.0f}/y win {sum(1 for x in u if x > 0) / n * 100:.1f}% ${mu:+.0f}/tr t{mu / (sd / math.sqrt(n)):+.1f} | era {era}"
                    f" | last6y {sum(rec) / max(1, len(rec)):+.0f}/tr n{len(rec)}")
        for side in ("L", "S"):
            for k in KS:
                tr = [x for x in self.trades if x[0] == side and x[1] == k]
                if side == "L" and k != 0.30:
                    continue
                self.set_runtime_statistic(f"VR {side} K{k:.2f} all", st(tr))
                for rg in ("DN50", "DN200", "DN20"):
                    if side == "S" or k == 0.30:
                        self.set_runtime_statistic(f"VR {side} K{k:.2f} {rg}", st([x for x in tr if x[6][rg]]))
                        if side == "L":
                            self.set_runtime_statistic(f"VR {side} K{k:.2f} not {rg}", st([x for x in tr if not x[6][rg]]))
        # eval plans (K 0.30)
        cal = sorted(set(self.cal))
        L = {x[3]: x[2] for x in self.trades if x[0] == "L" and x[1] == 0.30}
        S = {x[3]: x[2] for x in self.trades if x[0] == "S" and x[1] == 0.30}
        plans = {}
        plans["L"] = [L.get(d) for d in cal]
        for rg in ("DN50", "DN200", "DN20"):
            plans["LS" + rg[2:]] = [(S.get(d) if self.reg.get(d, {}).get(rg) else L.get(d)) for d in cal]
        plans["S50"] = [(S.get(d) if self.reg.get(d, {}).get("DN50") else None) for d in cal]
        dn_starts = [i for i, d in enumerate(cal) if self.reg.get(d, {}).get("DN50") and i < len(cal) - 120]
        all_starts = list(range(0, len(cal) - 120))
        for name, seq in plans.items():
            cells = []
            for lab, starts in (("all", all_starts), ("DN50 starts", dn_starts)):
                res = [self._chain(seq, s0) for s0 in starts]
                ok = [r for r in res if r[2]]
                if not res:
                    continue
                cells.append(f"{lab}: " + (f"{len(ok) / sum(r[1] for r in res) * 100:.0f}%/{sum(r[0] for r in ok) / len(ok):.0f}d/${sum(r[1] for r in res) / len(res) * 60:.0f}" if ok else "0%"))
            self.set_runtime_statistic(f"VR25 {name}", " | ".join(cells))
        self.set_runtime_statistic("VR info", f"days {len(cal)} last6y, DN50 share {sum(1 for d in cal if self.reg.get(d, {}).get('DN50')) / max(1, len(cal)) * 100:.0f}%")
