# region imports
from AlgorithmImports import *
import math
import random
# endregion
#
# "GOLD MORNING STAR STRATEGY" (owner 2026-11-08 pasted a social-media pitch:
# 81% of 1,000 simulated FTMO challenges passed, 512 trades in 5 years, 43%
# winners, avg win ~2x avg loss, max DD 7.5%, +$137k on 100K). Tested INSIDE
# QuantConnect on minute data built into clock-hour bars; aggregates only.
# Rules (as pitched) and test details FIXED BEFORE RESULTS:
#   1-hour chart. LONG: the third candle closes above MA14 and MA200 of hourly
#   closes. Morning star: candle 1 bearish with a long body (> mean body of the
#   10 hours before), candle 2 small (body <= 0.3 x body 1), candle 3 bullish
#   with a long body and a close above the middle of candle 1's body.
#   Entry: buy stop one tick above candle 3's high, valid for the next hour (V1)
#   or the next 3 hours (V3); filled at the worse of the stop and the minute open.
#   Stop: one tick below the lowest low of the three candles; target 2 R.
#   SHORT: the mirror (evening star below both MAs). One position at a time.
#   Exits checked on minute bars (stop first if both; gaps fill at the open).
# Variants: market GC (gold, as pitched) / NQ; MA type SMA / EMA; holding HOLD
#   (overnight allowed, as on FTMO) / FLAT (out by 16:44 ET, no entries
#   16:00-18:00 = Lucid rule); entry validity V1 / V3.
# Costs per round trip in points: GC 0.30 (spread + fees, ~$30 per 100 oz),
#   NQ 1.25. Results in R (risk = entry - stop) net of costs.
# FTMO phase 1 (100K, 1% = $1,000 risk per trade = 1 R): pass at +10 R, fail
#   at -10 R from the start or a day <= -5 R (closed trades; an open trade can
#   add at most 1 R more, ignored), no time limit but "unfinished" after 252
#   trading days; (a) sequential starts every 5th trading day, (b) 1,000
#   bootstrap shuffles of the trade sequence (as the pitch's simulation).
# Eras 2010-13 / 14-17 / 18-21 / 22-26 and the pitch's window 2021-11..2026-10.

START = (2010, 1, 1)
END = (2026, 12, 31)
COST = {"GC": 0.30, "NQ": 1.25}
TICK = {"GC": 0.10, "NQ": 0.25}
ERAS = (("10-13", 2010, 2013), ("14-17", 2014, 2017), ("18-21", 2018, 2021), ("22-26", 2022, 2026))


class Variant:
    def __init__(self, mk, ma, hold, val):
        self.mk, self.ma, self.hold, self.val = mk, ma, hold, val
        self.pend = None
        self.pos = None
        self.trades = []            # (R, exit date (session), year, month string)


class MorningStarInQC(QCAlgorithm):

    def initialize(self):
        self.set_start_date(*START)
        self.set_end_date(*END)
        self.set_cash(1_000_000)
        self.fut = {}
        for mk, tk in (("GC", Futures.Metals.GOLD), ("NQ", Futures.Indices.NASDAQ_100_E_MINI)):
            f = self.add_future(tk, Resolution.MINUTE, fill_forward=False,
                                data_normalization_mode=DataNormalizationMode.RAW,
                                data_mapping_mode=DataMappingMode.OPEN_INTEREST,
                                contract_depth_offset=0, extended_market_hours=True)
            f.set_filter(0, 180)
            self.fut[mk] = f
        self.st = {mk: {"agg": None, "hk": None, "bars": [], "sma14": None, "sma200": None, "ema14": None,
                        "ema200": None, "mapped": None, "last": None} for mk in self.fut}
        self.vars = [Variant(mk, ma, hold, val) for mk in self.fut for ma in ("SMA", "EMA")
                     for hold in ("HOLD", "FLAT") for val in (1, 3)]

    # ---------------------------------------------------------------- helpers
    def _close(self, v, px, t):
        p = v.pos
        r = ((px - p["e"]) * p["d"] - COST[v.mk]) / p["risk"]
        sd = (t + timedelta(hours=6)).date()
        v.trades.append((r, sd, t.year, f"{t.year}-{t.month:02d}"))
        v.pos = None

    def _hour_bar(self, mk, b, t):
        s = self.st[mk]
        bars = s["bars"]
        bars.append(b)
        if len(bars) > 220:
            bars.pop(0)
        closes = [x[3] for x in bars]
        c = b[3]
        s["ema14"] = c if s["ema14"] is None else s["ema14"] + (c - s["ema14"]) * 2 / 15
        s["ema200"] = c if s["ema200"] is None else s["ema200"] + (c - s["ema200"]) * 2 / 201
        if len(bars) < 211:
            return
        sma14 = sum(closes[-14:]) / 14
        sma200 = sum(closes[-200:]) / 200
        b1, b2, b3 = bars[-3], bars[-2], bars[-1]
        body = lambda x: abs(x[3] - x[0])
        mb = sum(body(x) for x in bars[-13:-3]) / 10
        sig = 0
        if (b1[3] < b1[0] and body(b1) > mb and body(b2) <= 0.3 * body(b1) and b3[3] > b3[0]
                and body(b3) > mb and b3[3] > (b1[0] + b1[3]) / 2):
            sig = 1
        elif (b1[3] > b1[0] and body(b1) > mb and body(b2) <= 0.3 * body(b1) and b3[3] < b3[0]
              and body(b3) > mb and b3[3] < (b1[0] + b1[3]) / 2):
            sig = -1
        if sig == 0:
            return
        m = t.hour * 60 + t.minute
        for v in self.vars:
            if v.mk != mk or v.pos is not None:
                continue
            f14, f200 = (sma14, sma200) if v.ma == "SMA" else (s["ema14"], s["ema200"])
            if sig == 1 and not (c > f14 and c > f200):
                continue
            if sig == -1 and not (c < f14 and c < f200):
                continue
            if v.hold == "FLAT" and 16 * 60 <= m < 18 * 60:
                continue
            lo3 = min(b1[2], b2[2], b3[2])
            hi3 = max(b1[1], b2[1], b3[1])
            if sig == 1:
                v.pend = {"d": 1, "lvl": b3[1] + TICK[mk], "sl": lo3 - TICK[mk], "until": t + timedelta(hours=v.val)}
            else:
                v.pend = {"d": -1, "lvl": b3[2] - TICK[mk], "sl": hi3 + TICK[mk], "until": t + timedelta(hours=v.val)}

    # ---------------------------------------------------------------- data
    def on_data(self, data: Slice):
        t = self.time
        m = t.hour * 60 + t.minute
        for mk, f in self.fut.items():
            bar = data.bars.get(f.symbol)
            if bar is None:
                continue
            s = self.st[mk]
            o, h, l, c = float(bar.open), float(bar.high), float(bar.low), float(bar.close)
            if s["mapped"] is not None and f.mapped != s["mapped"]:
                for v in self.vars:
                    if v.mk == mk:
                        if v.pos is not None:
                            self._close(v, s["last"], t)
                        v.pend = None
                s["bars"], s["agg"], s["ema14"], s["ema200"] = [], None, None, None
            s["mapped"] = f.mapped
            # positions / pending orders on this minute
            for v in self.vars:
                if v.mk != mk:
                    continue
                if v.pos is not None:
                    p = v.pos
                    if p["d"] == 1:
                        if l <= p["sl"]:
                            self._close(v, min(p["sl"], o), t)
                        elif h >= p["tp"]:
                            self._close(v, max(p["tp"], o), t)
                    else:
                        if h >= p["sl"]:
                            self._close(v, max(p["sl"], o), t)
                        elif l <= p["tp"]:
                            self._close(v, min(p["tp"], o), t)
                    if v.pos is not None and v.hold == "FLAT" and 16 * 60 + 44 <= m < 18 * 60:
                        self._close(v, c, t)
                elif v.pend is not None:
                    pd_ = v.pend
                    if t > pd_["until"] or (v.hold == "FLAT" and 16 * 60 + 30 <= m < 18 * 60):
                        v.pend = None
                    elif (pd_["d"] == 1 and h >= pd_["lvl"]) or (pd_["d"] == -1 and l <= pd_["lvl"]):
                        e = max(pd_["lvl"], o) if pd_["d"] == 1 else min(pd_["lvl"], o)
                        risk = (e - pd_["sl"]) * pd_["d"]
                        v.pend = None
                        if risk > 0:
                            v.pos = {"d": pd_["d"], "e": e, "sl": pd_["sl"], "tp": e + pd_["d"] * 2 * risk, "risk": risk}
                            # same-minute stop check (conservative)
                            if (pd_["d"] == 1 and l <= pd_["sl"]) or (pd_["d"] == -1 and h >= pd_["sl"]):
                                self._close(v, pd_["sl"], t)
            # hourly aggregation (bar end times; hour bar = minutes ending (HH:00, HH+1:00])
            hk = (t - timedelta(minutes=1)).replace(minute=0, second=0, microsecond=0)
            if s["hk"] is not None and hk != s["hk"] and s["agg"] is not None:
                self._hour_bar(mk, s["agg"], s["hk"] + timedelta(hours=1))
                s["agg"] = None
            s["hk"] = hk
            a = s["agg"]
            s["agg"] = [o, h, l, c] if a is None else [a[0], max(a[1], h), min(a[2], l), c]
            s["last"] = c

    # ---------------------------------------------------------------- results
    def _ftmo(self, days_r):
        """days_r: list of per-day lists of trade R -> (pass, fail, unfinished) shares."""
        res = []
        n = len(days_r)
        for s0 in range(0, max(1, n - 1), 5):
            eq, out = 0.0, "u"
            for i in range(s0, min(n, s0 + 252)):
                run, mn = eq, eq
                for r in days_r[i]:
                    run += r
                    mn = min(mn, run)
                if mn <= -10.0 or mn - eq <= -5.0:
                    out = "f"
                    break
                eq = run
                if eq >= 10.0:
                    out = "p"
                    break
            res.append(out)
        k = len(res)
        return (sum(1 for x in res if x == "p") / k * 100, sum(1 for x in res if x == "f") / k * 100) if k else (0, 0)

    def _boot(self, rs, ntr_year):
        rnd = random.Random(7)
        p = f_ = 0
        cap = int(ntr_year)
        for _ in range(1000):
            eq = 0.0
            out = "u"
            for j in range(cap):
                eq += rs[rnd.randrange(len(rs))]
                if eq <= -10.0:
                    out = "f"
                    break
                if eq >= 10.0:
                    out = "p"
                    break
            p += out == "p"
            f_ += out == "f"
        return p / 10.0, f_ / 10.0

    def on_end_of_algorithm(self):
        for v in self.vars:
            if v.pos is not None:
                self._close(v, self.st[v.mk]["last"], self.time)
            tr = v.trades
            if len(tr) < 30:
                self.set_runtime_statistic(f"MS {v.mk} {v.ma} {v.hold} V{v.val}", f"n {len(tr)}")
                continue
            rs = [x[0] for x in tr]
            n = len(rs)
            yrs = max(1.0, (tr[-1][1] - tr[0][1]).days / 365.25)
            mu = sum(rs) / n
            sd = math.sqrt(sum((x - mu) ** 2 for x in rs) / (n - 1))
            wins = [x for x in rs if x > 0]
            loss = [x for x in rs if x <= 0]
            cum = peak = mdd = 0.0
            for x in rs:
                cum += x
                peak = max(peak, cum)
                mdd = min(mdd, cum - peak)
            era = []
            for lab, a, b in ERAS:
                re = [x[0] for x in tr if a <= x[2] <= b]
                era.append(f"{lab} {sum(re) / len(re):+.2f}/{len(re)}" if re else f"{lab} -")
            pw = [x[0] for x in tr if "2021-11" <= x[3] <= "2026-10"]
            days = {}
            for x in tr:
                days.setdefault(x[1], []).append(x[0])
            # include empty days between first and last trade day for the sequential FTMO test
            d0, d1 = tr[0][1], tr[-1][1]
            seq = []
            d = d0
            while d <= d1:
                if d.weekday() < 5:
                    seq.append(days.get(d, []))
                d += timedelta(days=1)
            fp, ff = self._ftmo(seq)
            bp, bf = self._boot(rs, n / yrs)
            key = f"MS {v.mk} {v.ma} {v.hold} V{v.val}"
            self.set_runtime_statistic(key, f"{n / yrs:.0f}/y win {len(wins) / n * 100:.0f}% avgW {sum(wins) / max(1, len(wins)):.2f} "
                                       f"avgL {sum(loss) / max(1, len(loss)):.2f} {mu:+.3f}R t{mu / (sd / math.sqrt(n)):+.1f} maxDD {mdd:.0f}R | " + " ".join(era))
            self.set_runtime_statistic(key + " ftmo", f"pitch window 21-26: {sum(pw) / max(1, len(pw)):+.3f}R n{len(pw)} sum {sum(pw):+.0f}R | "
                                       f"FTMO seq pass {fp:.0f}% fail {ff:.0f}% | boot pass {bp:.0f}% fail {bf:.0f}%")
