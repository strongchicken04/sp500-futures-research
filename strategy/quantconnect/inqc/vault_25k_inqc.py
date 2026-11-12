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
# v2 output: per scheme and max trades / day: pass per attempt / mean trading days to a pass /
#   fees / share of start days that pass within 250 days.
# Output: per variant pass per attempt, mean trading days to a pass, mean
#   evaluations bought, mean fees; ranked by fees, then days. Starts every
#   trading day of the window with >= 120 days left; an attempt chain stops
#   after 250 trading days (counted as not passed).

START = (2020, 7, 1)
END = (2026, 12, 31)
WIN0 = "2020-08-10"
PRICE = 28530.0
TP_PT, SL_PT = 40.0, 75.0
# v4 (owner 2026-11-11: "test SL $1,000 and TP $625", per NQ like the original $800 / $1,500):
# TP 31.25 pt / SL 50 pt vs the original 40 / 75; sizes 3-10 MNQ (a 50-pt stop fits up to 9 MNQ).
TPS = {"40/75": (40.0, 75.0), "52/83": (625 / 12.0, 1000 / 12.0), "53/83": (640 / 12.0, 1000 / 12.0)}
# v6 (owner: "6 MNQ, aim for more points: fixed SL $1,000 / TP $625 per position"): 6 MNQ ->
# TP 52.1 pt ($625 gross; 2 wins = $1,220 net, short of $1,250) and 53.3 pt ($640 gross = $625 net,
# 2 wins = exactly the target at 50% consistency); SL 83.3 pt = $1,000 = the whole drawdown.
# v5 (owner: "why 20 days if 1 loss = blow and 2 wins = pass?"): path diagnostics for PCT 40/75 6 MNQ
# and PCT 31/50 9 MNQ, first trade of the day: share of days with a signal, wins needed, signal
# days per passing / failed attempt, attempts per pass.
# v7 (owner 2026-11-12: "what if the 17:00 (Prague) candle already traded?" = the candle 09:30-10:00 CT,
# closing 17:00 Prague / 10:00 CT): start C1000 (first entry candle opens 10:00 CT, as before) vs C0930
# (the 09:30 CT candle also counts); TP 40 / SL 75 only.
TPS = {"40/75": (40.0, 75.0)}
KEYS = [ex + tk + "@" + st for ex in ("PTS", "PCT") for tk in TPS for st in ("C1000", "C0930")]
MNQ_PV, MNQ_COST = 2.0, 2.5
FEE = 60.0
# v8 (owner 2026-11-12, 25K FUNDED payout rules): max DD $1,000 (EOD trailing, locks at +$100 once an EOD
# balance reaches +$1,100 - assumed as in the eval, and locked at +$100 after the first payout), no
# consistency, no daily loss limit; a payout needs 5 winning days of >= $100 since the last payout and is
# at most 50% of the profit balance and at most $1,000; the trader keeps 90%. Policies: ASAP (request as
# soon as eligible with >= $250), P500 (request when >= $500 is available), P1000 (wait for the full
# $1,000). Each funded account runs up to 250 trading days or until it breaches; starts every 5th day.
# Output per signal / max trades a day / policy / size: mean net payouts per account in that year,
# share of accounts with >= 1 payout, mean payouts count, breach rate within the year.
FUND_SIZES = ("FIX3", "FIX4", "FIX6", "FIX8", "FIX10", "ROOM1")
FUND_POL = {"ASAP": 250.0, "P500": 500.0, "P1000": 1000.0}


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
        self.pos = {k: None for k in KEYS}
        self.ntoday = {k: 0 for k in KEYS}
        self.days = {k: {} for k in KEYS}       # date -> list of (pts_per_contract, stop_pts, tp_pts)
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
            self.ntoday = {k: 0 for k in KEYS}
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
        if not (11 * 60 <= m <= 15 * 60):
            return
        if cc > self.mid + 0.30 * atr and cc > vwap:
            for ex in self.pos:
                if self.pos[ex] is not None or self.ntoday[ex] >= 3:
                    continue
                if ex.endswith("@C1000") and m < 11 * 60 + 30:
                    continue
                tpp, slp = TPS[ex[3:].split("@")[0]]
                tpd, sld = (tpp, slp) if ex.startswith("PTS") else (cc * tpp / PRICE, cc * slp / PRICE)
                scale = 1.0 if ex.startswith("PTS") else PRICE / cc
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

    def _funded(self, seq, s0, scheme, maxt, minpay):
        bal = peak = 0.0
        locked = False
        wd = 0
        paid = 0.0
        npay = 0
        i = s0
        while i < len(seq) and i - s0 < 250:
            day = seq[i]
            i += 1
            line = 100.0 if locked else peak - 1000.0
            run = bal
            for k, (pts, sl, tp) in enumerate(day):
                if k >= maxt:
                    break
                stop_usd = sl * MNQ_PV + MNQ_COST
                if scheme.startswith("FIX"):
                    n = int(scheme[3:])
                else:
                    n = int((run - line - 50.0) / stop_usd)
                n = max(1, min(20, n))
                run += pts * MNQ_PV * n - MNQ_COST * n
                if run <= line:
                    return paid, npay, True
            if run - bal >= 100.0:
                wd += 1
            bal = run
            peak = max(peak, bal)
            if peak >= 1100.0:
                locked = True
            amt = min(0.5 * bal, 1000.0)
            if wd >= 5 and amt >= minpay:
                bal -= amt
                paid += 0.9 * amt
                npay += 1
                wd = 0
                locked = True
        return paid, npay, False

    def on_end_of_algorithm(self):
        if any(v is not None for v in self.pos.values()):
            for ex in self.pos:
                if self.pos[ex] is not None:
                    self._book(ex, self.pos[ex]["e"], self.time)
        cal = sorted(set(self.cal))
        n_tr = {ex: sum(len(v) for v in self.days[ex].values()) for ex in self.days}
        self.set_runtime_statistic("V25 info", f"{cal[0]}..{cal[-1]} days {len(cal)} trades " + " ".join(f"{k} {v}" for k, v in n_tr.items()))
        # v2 output: the full speed / cost frontier (day stop dropped: it changed nothing in v1)
        for ex in KEYS:
            seq = [self.days[ex].get(d, []) for d in cal]
            cells = []
            for maxt in (1, 2, 3):
                res = [self._attempt_chain(seq, s0, "FIX6", False, maxt, 0) for s0 in range(0, len(seq) - 120)]
                ok = [r for r in res if r[2]]
                evals = sum(r[1] for r in res) / len(res)
                ppa = len(ok) / sum(r[1] for r in res) * 100
                dd = sum(r[0] for r in ok) / len(ok) if ok else 999
                cells.append(f"t{maxt} {ppa:.0f}%/{dd:.0f}d/${evals * FEE:.0f}")
            self.set_runtime_statistic(f"V25 {ex} FIX6", " | ".join(cells))
        for ex in KEYS:
            seq = [self.days[ex].get(d, []) for d in cal]
            starts = range(0, max(1, len(seq) - 250), 5)
            for maxt in (1, 3):
                for pol, mp in FUND_POL.items():
                    cells = []
                    for sc in FUND_SIZES:
                        res = [self._funded(seq, s0, sc, maxt, mp) for s0 in starts]
                        nn = len(res)
                        cells.append(f"{sc[:1]}{sc[-2:].lstrip('X').lstrip('M')} ${sum(r[0] for r in res) / nn:.0f} "
                                     f"{sum(1 for r in res if r[1] > 0) / nn * 100:.0f}% {sum(r[1] for r in res) / nn:.1f}x b{sum(1 for r in res if r[2]) / nn * 100:.0f}")
                    self.set_runtime_statistic(f"F {ex} t{maxt} {pol}", " | ".join(cells))
        for ex, n in [(k, 6) for k in KEYS]:
            seq = [self.days[ex].get(d, []) for d in cal]
            sig_share = sum(1 for d in seq if d) / len(seq) * 100
            first = [d[0] for d in seq if d]
            win1 = sum(1 for x in first if x[0] > 0) / len(first) * 100
            w_usd = first[0][2] * MNQ_PV * n - MNQ_COST * n
            l_usd = first[0][1] * MNQ_PV * n + MNQ_COST * n
            # walk every attempt (start each day) and record its length in days / signal days and outcome
            att = []
            for s0 in range(0, len(seq) - 120):
                i, eq, peak, best, td, sd = s0, 0.0, 0.0, 0.0, 0, 0
                out = None
                while i < len(seq) and i - s0 < 250:
                    day = seq[i]
                    i += 1
                    line = 100.0 if peak >= 1100.0 else peak - 1000.0
                    if day:
                        sd += 1
                        r = eq + day[0][0] * MNQ_PV * n - MNQ_COST * n
                        if r <= line:
                            out = "bust"
                            break
                        best = max(best, r - eq)
                        eq = r
                        td += 1
                        peak = max(peak, eq)
                        if eq >= 1250.0 and best <= 0.5 * eq and td >= 2:
                            out = "pass"
                            break
                if out:
                    att.append((out, i - s0, sd))
            ps = [a for a in att if a[0] == "pass"]
            bs = [a for a in att if a[0] == "bust"]
            self.set_runtime_statistic(f"V25D {ex} {n}MNQ",
                f"days with a signal {sig_share:.0f}% | 1st-trade win {win1:.1f}% | win ${first[0][2] * MNQ_PV * n - MNQ_COST * n:.0f}"
                f" | single attempt: pass {len(ps) / len(att) * 100:.0f}% bust {len(bs) / len(att) * 100:.0f}%"
                f" | pass takes {sum(a[1] for a in ps) / len(ps):.1f} d ({sum(a[2] for a in ps) / len(ps):.1f} signal d)"
                f" | bust takes {sum(a[1] for a in bs) / len(bs):.1f} d ({sum(a[2] for a in bs) / len(bs):.1f} signal d)")
            # per-trade stats of the signal in the window
            pts = [x[0] for v in self.days[ex].values() for x in v]
            if pts:
                wins = sum(1 for x in pts if x > 0)
                self.set_runtime_statistic(f"V25 {ex} signal", f"{len(pts)} trades win {wins / len(pts) * 100:.1f}% mean {sum(pts) / len(pts):+.1f} pt/contract")
