# region imports
from AlgorithmImports import *
from datetime import date as _date, timedelta
import bisect
# endregion
#
# EXTREME-UPSIDE RESEARCH - STAGE 2 VALIDATION 4: FINRA SHORT-INTEREST TIMESTAMPS (owner 2026-11-24). Aggregates only.
# FINRA rule: settlement dates = the 15th (previous settlement day if not one) and the last settlement day of the
# month; firms report 2 business days later; FINRA publishes 7 business days after the settlement date.
# Here the rule calendar is built from NYSE trading days (SPY bars) - DTC holidays on which NYSE trades
# (Columbus / Veterans Day) can shift a real publication date by one day; this is reported as tolerance.
# For every change of a symbol's short_interest value in FINRAShortInterestUniverse (tracked: first 4,000 symbols +
# GME AMC AAPL TSLA BBBY) the algorithm date d (= record end_time) is mapped to the first trading session in which the
# value is usable U(d), and compared with the latest rule publication date P <= U(d):
#   n = trading days from P to U(d). n = 1 -> usable the session after publication (= "publication + 1 trading day"
#   rule, no extra delay needed); n = 0 -> visible on the publication day itself (needs +1); n >= 2 -> QC lags.
# Also: record time / end_time vs algo time, consistency of previous_short_interest with the prior value, cycles
# without a change, gaps in delivery (missing days), long unchanged runs (stale forward-fill), last delivery date.

TRACK_EXTRA = ("GME", "AMC", "AAPL", "TSLA", "BBBY")


class XupS2SI(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2018, 1, 1)
        self.set_end_date(2026, 11, 20)
        self.set_cash(100000)
        spy = self.add_equity("SPY", Resolution.DAILY).symbol
        h = self.history(spy, datetime(2017, 11, 1), datetime(2026, 11, 21), Resolution.DAILY)
        days = set()
        for ix in h.index:
            t = ix[1] if isinstance(ix, tuple) else ix
            days.add(t.date() if t.hour >= 9 else (t - timedelta(days=1)).date())
        self.td = sorted(days)
        self.tdi = {d: i for i, d in enumerate(self.td)}
        # rule calendar
        self.settle = []
        y, m = 2017, 11
        while (y, m) <= (2026, 11):
            mid = self._prev_td(_date(y, m, 15))
            nm = _date(y + (m == 12), m % 12 + 1, 1)
            end = self._prev_td(nm - timedelta(days=1))
            self.settle += [mid, end]
            y, m = nm.year, nm.month
        self.pub = sorted(self.td[self.tdi[s] + 7] for s in self.settle if s in self.tdi and self.tdi[s] + 7 < len(self.td))
        self.universe_settings.resolution = Resolution.DAILY
        self.add_universe(FINRAShortInterestUniverse, self._sel)
        self.track = set()
        self.last = {}        # sid -> (si, prev_si, last_seen_date, last_change_date)
        self.nhist = {}
        self.sdist = {}
        self.prev_ok = [0, 0]
        self.gaps = 0
        self.gapdays = []
        self.stale = 0
        self.examples = {}
        self.times = []
        self.last_delivery = None
        self.deliveries = 0
        self.zero = [0, 0]
        self.changes_per_cycle = {}

    def _prev_td(self, d):
        i = bisect.bisect_right(self.td, d) - 1
        return self.td[i] if i >= 0 else d

    def _next_td(self, d):
        i = bisect.bisect_left(self.td, d)
        return self.td[i] if i < len(self.td) else d

    def _sel(self, data):
        d = self.time.date()
        self.deliveries += 1
        self.last_delivery = d
        U = self._next_td(d)
        ui = self.tdi.get(U)
        for x in data:
            sym = x.symbol
            sid = str(sym.id)
            if sid not in self.track:
                if len(self.track) < 4000 or sym.value in TRACK_EXTRA:
                    self.track.add(sid)
                else:
                    continue
            try:
                si = float(x.short_interest)
                psi = float(x.previous_short_interest)
            except Exception:
                continue
            self.zero[1] += 1
            if si <= 0:
                self.zero[0] += 1
            if len(self.times) < 3:
                self.times.append(f"algo {d} t {x.time} end {x.end_time}")
            lv = self.last.get(sid)
            if lv is None:
                self.last[sid] = (si, psi, d, d)
                continue
            gap = (d - lv[2]).days
            if gap > 4:
                self.gaps += 1
                self.gapdays.append(gap)
            lc = lv[3]
            if si != lv[0]:
                # change observed
                self.prev_ok[1] += 1
                if abs(psi - lv[0]) <= max(1.0, 1e-6 * abs(lv[0])):
                    self.prev_ok[0] += 1
                if ui is not None:
                    j = bisect.bisect_right(self.pub, U) - 1
                    if j >= 0:
                        n = ui - self.tdi[self.pub[j]]
                        self.nhist[n] = self.nhist.get(n, 0) + 1
                        # signed distance to nearest publication date (detect changes before publication)
                        k = bisect.bisect_left(self.pub, U)
                        cands = [self.pub[c] for c in (k - 1, k) if 0 <= c < len(self.pub)]
                        best = min(cands, key=lambda p: abs(ui - self.tdi[p]))
                        sd = ui - self.tdi[best]
                        self.sdist[sd] = self.sdist.get(sd, 0) + 1
                        cyc = self.pub[j]
                        self.changes_per_cycle[(sid, cyc)] = self.changes_per_cycle.get((sid, cyc), 0) + 1
                if sym.value in TRACK_EXTRA and d.year == 2021 and d.month <= 4:
                    self.examples.setdefault(sym.value, []).append(d.strftime("%m%d"))
                lc = d
            elif (d - lc).days > 50:
                self.stale += 1
                lc = d  # count each 50-day stale run once
            self.last[sid] = (si, psi, d, lc)
        return []

    def on_end_of_algorithm(self):
        S = self.set_runtime_statistic
        tot = max(1, sum(self.nhist.values()))
        S("SI n = trading days publication->usable", " ".join(f"{k}:{100.0 * v / tot:.1f}%" for k, v in sorted(self.nhist.items()) if v / tot >= 0.001)[:198])
        tot2 = max(1, sum(self.sdist.values()))
        S("SI signed distance to nearest publication", " ".join(f"{k}:{100.0 * v / tot2:.1f}%" for k, v in sorted(self.sdist.items()) if v / tot2 >= 0.001)[:198])
        S("SI changes", f"{tot} changes, {len(self.track)} symbols | previous_short_interest == prior value {100.0 * self.prev_ok[0] / max(1, self.prev_ok[1]):.1f}% | multi-change cycles {100.0 * sum(1 for v in self.changes_per_cycle.values() if v > 1) / max(1, len(self.changes_per_cycle)):.1f}%")
        self.gapdays.sort()
        S("SI gaps / stale", f"delivery gaps >4d {self.gaps} (p50 {self.gapdays[len(self.gapdays) // 2] if self.gapdays else 0}d) | unchanged >50d runs {self.stale} | si<=0 {100.0 * self.zero[0] / max(1, self.zero[1]):.2f}% | deliveries {self.deliveries} last {self.last_delivery}")
        S("SI record times", " | ".join(self.times)[:198])
        p21 = [p.strftime("%m%d") for p in self.pub if p.year == 2021 and p.month <= 4]
        s21 = [s.strftime("%m%d") for s in self.settle if s.year == 2021 and s.month <= 4]
        S("SI rule 2021 settle / publish", f"settle {' '.join(s21)} | publish {' '.join(p21)}")
        for tk in TRACK_EXTRA:
            if tk in self.examples:
                S(f"SI {tk} 2021 change algo dates", " ".join(self.examples[tk])[:198])
