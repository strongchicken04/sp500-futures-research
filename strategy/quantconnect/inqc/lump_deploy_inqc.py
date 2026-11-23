# region imports
from AlgorithmImports import *
import math
# endregion
#
# HOW TO DEPLOY A LUMP SUM (owner 2026-11-23: "I have 90,000 to invest - best way? some advanced cost averaging?
# consider the current dip on NQ / ES"). SPY and QQQ daily, dividend-adjusted (total return), 1999-2026, INSIDE
# QuantConnect, aggregates only. FIXED BEFORE RESULTS, monthly steps at the first trading day of each month,
# uninvested cash earns 0% (conservative for the waiting schemes - see the note in the report):
#   LS        everything at t0
#   DCA6      1/6 a month for 6 months;  DCA12  1/12 a month for 12 months
#   DIP12     12 monthly tranches of 1/12; 2x the tranche when the price is >= 10% below its 52-week high,
#             everything left when >= 20% below; the rest at month 11
#   HALF      50% at t0, the rest 1/6 a month for 6 months; everything left when >= 15% below the high
#   TREND200  invest everything left as soon as a month starts above the 200-day SMA; otherwise wait (max 12)
# Outcome: value after 60 months (x initial); compared with LS on the same start: mean difference, share of
# starts that beat LS, median / worst outcome, worst drop of the portfolio value in the first 12 months.
# Start sets: ALL starts 2000-2021; DIP starts = t0 price 5-20% below the 52-week high; DEEP = > 20% below.

SCHEMES = ("LS", "DCA6", "DCA12", "DIP12", "HALF", "TREND200")


class LumpDeploy(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2026, 1, 2)
        self.set_end_date(2026, 1, 3)
        self.set_cash(100000)
        self.syms = {t: self.add_equity(t, Resolution.DAILY).symbol for t in ("SPY", "QQQ")}

    def on_end_of_algorithm(self):
        for tk, sym in self.syms.items():
            h = self.history(sym, datetime(1998, 1, 1), datetime(2026, 12, 31), Resolution.DAILY)
            if h is None or h.empty:
                self.set_runtime_statistic(f"LD {tk}", "no data")
                continue
            closes = [float(x) for x in h["close"].values]
            dates = [ix[1].date() if isinstance(ix, tuple) else ix.date() for ix in h.index]
            n = len(closes)
            # month-start indices
            ms = [i for i in range(1, n) if dates[i].month != dates[i - 1].month]
            hi52 = []
            sma200 = []
            for i in range(n):
                a = max(0, i - 252)
                hi52.append(max(closes[a:i + 1]))
                b = max(0, i - 199)
                sma200.append(sum(closes[b:i + 1]) / (i + 1 - b))
            res = {s: {"ALL": [], "DIP": [], "DEEP": []} for s in SCHEMES}
            for k, i0 in enumerate(ms):
                if dates[i0].year < 2000 or k + 60 >= len(ms):
                    continue
                dd0 = closes[i0] / hi52[i0] - 1.0
                sets = ["ALL"] + (["DIP"] if -0.20 <= dd0 <= -0.05 else []) + (["DEEP"] if dd0 < -0.20 else [])
                iend = ms[k + 60]
                yr1 = ms[k + 12]
                for s in SCHEMES:
                    cash, units = 1.0, 0.0
                    left = 12 if s in ("DCA12", "DIP12", "TREND200") else 6
                    for j in range(0, 12):
                        i = ms[k + j]
                        px = closes[i]
                        buy = 0.0
                        if s == "LS":
                            buy = cash if j == 0 else 0.0
                        elif s == "DCA6":
                            buy = 1.0 / 6 if j < 6 else 0.0
                        elif s == "DCA12":
                            buy = 1.0 / 12
                        elif s == "DIP12":
                            dd = px / hi52[i] - 1.0
                            buy = cash if (dd <= -0.20 or j == 11) else (2.0 / 12 if dd <= -0.10 else 1.0 / 12)
                        elif s == "HALF":
                            dd = px / hi52[i] - 1.0
                            buy = 0.5 if j == 0 else (cash if dd <= -0.15 else (0.5 / 6 if j <= 6 else 0.0))
                            if j == 6:
                                buy = cash
                        elif s == "TREND200":
                            buy = cash if (px > sma200[i] or j == 11) else 0.0
                        buy = min(cash, buy)
                        units += buy / px
                        cash -= buy
                        if cash <= 1e-9:
                            break
                    # worst drop of the total value in the first 12 months (daily)
                    # recompute the path roughly: value with the final holdings schedule is complex - approximate
                    # with month-end values
                    end_val = cash + units * closes[iend]
                    # first-year path: simulate again month by month for the worst drop
                    c2, u2, pk, wd = 1.0, 0.0, 1.0, 0.0
                    for j in range(0, 12):
                        i = ms[k + j]
                        px = closes[i]
                        if s == "LS":
                            b = c2 if j == 0 else 0.0
                        elif s == "DCA6":
                            b = 1.0 / 6 if j < 6 else 0.0
                        elif s == "DCA12":
                            b = 1.0 / 12
                        elif s == "DIP12":
                            dd = px / hi52[i] - 1.0
                            b = c2 if (dd <= -0.20 or j == 11) else (2.0 / 12 if dd <= -0.10 else 1.0 / 12)
                        elif s == "HALF":
                            dd = px / hi52[i] - 1.0
                            b = 0.5 if j == 0 else (c2 if dd <= -0.15 else (0.5 / 6 if j <= 6 else 0.0))
                            if j == 6:
                                b = c2
                        else:
                            b = c2 if (px > sma200[i] or j == 11) else 0.0
                        b = min(c2, b)
                        u2 += b / px
                        c2 -= b
                        for d in range(i, ms[k + j + 1]):
                            val = c2 + u2 * closes[d]
                            pk = max(pk, val)
                            wd = min(wd, val / pk - 1.0)
                    for st in sets:
                        res[s][st].append((end_val, wd, k))
            for st in ("ALL", "DIP", "DEEP"):
                ls = {x[2]: x[0] for x in res["LS"][st]}
                for s in SCHEMES:
                    xs = res[s][st]
                    if len(xs) < 5:
                        continue
                    vals = sorted(x[0] for x in xs)
                    diff = [x[0] / ls[x[2]] - 1.0 for x in xs]
                    beat = sum(1 for d in diff if d > 1e-9) / len(diff) * 100
                    self.set_runtime_statistic(f"LD {tk} {st} {s}",
                        f"n {len(xs)} | 5y x{sum(vals) / len(vals):.2f} med x{vals[len(vals) // 2]:.2f} worst x{vals[0]:.2f} | vs LS {sum(diff) / len(diff) * 100:+.1f}% beats LS {beat:.0f}%"
                        f" | yr1 worst drop avg {sum(x[1] for x in xs) / len(xs) * 100:.0f}% min {min(x[1] for x in xs) * 100:.0f}%")
