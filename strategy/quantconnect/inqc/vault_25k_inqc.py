# region imports
from AlgorithmImports import *
import math
# endregion
#
# VAULT BREAK - POSITION SIZING FOR THE LUCID FLEX 25K EVALUATION (owner
# 2026-11-11: "$1,000 max DD, $1,250 target, 50% consistency, no daily loss
# limit, last 6 years only, optimal position sizing"). INSIDE QuantConnect,
# aggregates only. Rules FIXED BEFORE RESULTS:
#   Signal = Vault Break as specified (vault_break_inqc.py): midnight CT +
#   0.30 x ATR15, VWAP from midnight CT, 30-min close above both from the
#   candle opening 10:00 CT, long, TP 40 pt / SL 75 pt (the owner's $800 /
#   $1,500 per NQ), flat 14:30 CT; PCT variant: the same distances as % of
#   today's NQ (0.140% / 0.263%). Window: 2020-08-10 .. data end (~6 years).
#   Trades are generated once (per-contract points); sizing is simulated on
#   top. MNQ $2 / pt, cost $2.50 per MNQ round trip; max 20 MNQ (25K).
# Account: target +$1,250; trailing drawdown $1,000 from the end-of-day peak,
#   locked at +$100 once an end-of-day balance reaches +$1,100; intraday breach
#   (running P&L after each closed trade) kills the account; consistency: at the
#   pass the best day <= 50% of the profit (and >= 2 trading days); no daily
#   loss limit. A dead account buys a new evaluation (fee $60) next day.
# Sizing grid:
#   FIXn: n MNQ always (n = 1..8, and 10 = the owner's 1 NQ).
#   ROOM1 / ROOM2: n = floor((room - $50) / stop $ per MNQ), the largest size
#     whose 1 (2) stop(s) still fit above the line; >= 1, <= 20.
#   +FIN: when the target is within one win (and the line is locked or the
#     win fits the room), size just to finish (+$20).
#   Management: max trades a day 1 / 2 / 3; day stop after +$X profit (none /
#     +$400 / +$600) - the consistency rule makes one huge day useless.
# Output: per variant pass per attempt, mean trading days to a pass, mean
#   evaluations bought, mean fees; ranked by fees, then days. Starts every
#   trading day of the window with >= 120 days left; an attempt chain stops
#   after 250 trading days (counted as not passed).

START = (2020, 7, 1)
END = (2026, 12, 31)
WIN0 = "2020-08-10"
PRICE = 28530.0
TP_PT, SL_PT = 40.0, 75.0
MNQ_PV, MNQ_COST = 2.0, 2.5
FEE = 60.0


class Vault25kInQC(QCAlgorithm):

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
        self.pos = {"PTS": None, "PCT": None}
        self.ntoday = {"PTS": 0, "PCT": 0}
        self.days = {"PTS": {}, "PCT": {}}       # date -> list of (pts_per_contract, stop_pts, tp_pts)
        self.cal = []

    def _book(self, ex, px, t):
        p = self.pos[ex]
        self.days[ex].setdefault(self.day, []).append(((px - p["e"]) * p["scale"], p["sld"], p["tpd"]))
        self.pos[ex] = None

    def on_data(self, data: Slice):
        bar = data.bars.get(self.f.symbol)
        if bar is None:
            return
        t = self.time
        m = t.hour * 60 + t.minute
        o, h, l, c, v = float(bar.open), float(bar.high), float(bar.low), float(bar.close), float(bar.volume)
        if 60 < m <= 18 * 60 and self.day != t.date():
            if self.day is not None and self.hi is not None:
                self.ranges.append(self.hi - self.lo)
                if len(self.ranges) > 15:
                    self.ranges.pop(0)
            self.day = t.date()
            if str(self.day) >= WIN0:
                self.cal.append(self.day)
            self.mid, self.hi, self.lo = o, h, l
            self.pv = self.vv = 0.0
            self.c30 = None
            self.mapped = self.f.mapped
            self.ntoday = {"PTS": 0, "PCT": 0}
        if self.day != t.date() or not (60 < m <= 18 * 60):
            return
        if self.f.mapped != self.mapped:
            for ex in self.pos:
                if self.pos[ex] is not None:
                    self._book(ex, c, t)
                self.ntoday[ex] = 3
            self.mapped = self.f.mapped
        self.hi, self.lo = max(self.hi, h), min(self.lo, l)
        self.pv += (h + l + c) / 3.0 * v
        self.vv += v
        vwap = self.pv / self.vv if self.vv > 0 else c
        for ex in self.pos:
            p = self.pos[ex]
            if p is None:
                continue
            if l <= p["sl"]:
                self._book(ex, min(p["sl"], o), t)
            elif h >= p["tp"]:
                self._book(ex, max(p["tp"], o), t)
            if self.pos[ex] is not None and m >= 15 * 60 + 30:
                self._book(ex, c, t)
        a = self.c30
        self.c30 = [o, h, l, c] if a is None else [a[0], max(a[1], h), min(a[2], l), c]
        if m % 30 != 0:
            return
        cc = self.c30[3]
        self.c30 = None
        if len(self.ranges) < 15 or str(self.day) < WIN0:
            return
        atr = sum(self.ranges) / 15.0
        if not (11 * 60 + 30 <= m <= 15 * 60):
            return
        if cc > self.mid + 0.30 * atr and cc > vwap:
            for ex in self.pos:
                if self.pos[ex] is not None or self.ntoday[ex] >= 3:
                    continue
                tpd, sld = (TP_PT, SL_PT) if ex == "PTS" else (cc * TP_PT / PRICE, cc * SL_PT / PRICE)
                scale = 1.0 if ex == "PTS" else PRICE / cc
                self.pos[ex] = {"e": cc, "tp": cc + tpd, "sl": cc - sld, "tpd": tpd * scale, "sld": sld * scale, "scale": scale}
                self.ntoday[ex] += 1

    # ------------------------------------------------------------------ sizing sim
    def _attempt_chain(self, seq, s0, scheme, fin, maxt, daystop):
        """seq: list of per-day lists of (pts, stop_pts, tp_pts) (PCT already re-scaled to today's points)."""
        T, DD = 1250.0, 1000.0
        i, evals = s0, 1
        eq = peak = 0.0
        days_traded, best = 0, 0.0
        while i < len(seq) and i - s0 < 250:
            day = seq[i]
            i += 1
            line = 100.0 if peak >= DD + 100.0 else peak - DD
            run = eq
            dead = False
            k = 0
            for pts, sl, tp in day:
                if k >= maxt or (daystop and run - eq >= daystop):
                    break
                stop_usd = (sl * MNQ_PV + MNQ_COST)
                win_usd = (tp * MNQ_PV - MNQ_COST)
                room = run - line
                if scheme.startswith("FIX"):
                    n = int(scheme[3:])
                else:
                    fit = 1 if scheme == "ROOM1" else 2
                    n = int((room - 50.0) / (stop_usd * fit))
                if fin and T - run <= win_usd * max(1, n):
                    need = int(math.ceil((T - run + 20.0) / win_usd))
                    n = min(n, need) if n > 0 else need
                n = max(1, min(20, n))
                run += pts * MNQ_PV * n - MNQ_COST * n
                k += 1
                if run <= line:
                    dead = True
                    break
            if k > 0:
                days_traded += 1
            if dead:
                evals += 1
                eq = peak = 0.0
                days_traded, best = 0, 0.0
                continue
            best = max(best, run - eq)
            eq = run
            peak = max(peak, eq)
            if eq >= T and best <= 0.5 * eq and days_traded >= 2:
                return i - s0, evals, True
        return i - s0, evals, False

    def on_end_of_algorithm(self):
        if self.pos["PTS"] is not None or self.pos["PCT"] is not None:
            for ex in self.pos:
                if self.pos[ex] is not None:
                    self._book(ex, self.pos[ex]["e"], self.time)
        cal = sorted(set(self.cal))
        n_tr = {ex: sum(len(v) for v in self.days[ex].values()) for ex in self.days}
        self.set_runtime_statistic("V25 info", f"{cal[0]}..{cal[-1]} days {len(cal)} trades PTS {n_tr['PTS']} PCT {n_tr['PCT']}")
        schemes = [f"FIX{n}" for n in (1, 2, 3, 4, 5, 6, 7, 8, 10)] + ["ROOM1", "ROOM2"]
        for ex in ("PTS", "PCT"):
            seq = [self.days[ex].get(d, []) for d in cal]
            rows = []
            for sc in schemes:
                for fin in (False, True):
                    if fin and sc.startswith("FIX"):
                        continue
                    for maxt in (1, 2, 3):
                        for ds in (0, 400, 600):
                            res = [self._attempt_chain(seq, s0, sc, fin, maxt, ds) for s0 in range(0, len(seq) - 120)]
                            ok = [r for r in res if r[2]]
                            if not res:
                                continue
                            evals = sum(r[1] for r in res) / len(res)
                            passes = len(ok)
                            ppa = passes / sum(r[1] for r in res) * 100
                            dd = sum(r[0] for r in ok) / len(ok) if ok else 999
                            fee = evals * FEE
                            share = passes / len(res) * 100
                            rows.append((fee if share > 50 else 1e9, dd, f"{sc}{'+FIN' if fin else ''} t{maxt} ds{ds}",
                                         ppa, dd, evals, fee, share))
            rows.sort()
            for j, r in enumerate(rows[:12]):
                self.set_runtime_statistic(f"V25 {ex} top{j:02d} {r[2]}", f"pass/att {r[3]:.0f}% {r[4]:.1f}d evals {r[5]:.2f} ${r[6]:.0f} chains passed {r[7]:.0f}%")
            ref = {f"FIX1 t3 ds0", "FIX3 t3 ds0", "FIX10 t3 ds0", "ROOM1 t3 ds0", "ROOM1+FIN t3 ds0"}
            for r in rows:
                if r[2] in ref:
                    self.set_runtime_statistic(f"V25 {ex} ref {r[2]}", f"pass/att {r[3]:.0f}% {r[4]:.1f}d evals {r[5]:.2f} ${r[6]:.0f} chains passed {r[7]:.0f}%")
            # per-trade stats of the signal in the window
            pts = [x[0] for v in self.days[ex].values() for x in v]
            if pts:
                wins = sum(1 for x in pts if x > 0)
                self.set_runtime_statistic(f"V25 {ex} signal", f"{len(pts)} trades win {wins / len(pts) * 100:.1f}% mean {sum(pts) / len(pts):+.1f} pt/contract")
