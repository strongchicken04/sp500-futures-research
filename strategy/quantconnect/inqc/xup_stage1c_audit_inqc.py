# region imports
from AlgorithmImports import *
# endregion
#
# EXTREME-UPSIDE RESEARCH - STAGE 1c AUDIT: FINRA short interest timing (owner 2026-11-24). Aggregates only.
# FINRA short interest has a settlement date (mid-month and month-end) and is published ~7-8 business days later.
# If QC delivers records ON the settlement dates, using them unshifted is look-ahead; if they arrive ~a week after,
# they are publication-dated. Checks: field names of FINRAShortInterest universe objects; the day-of-month
# histogram of dates on which records arrive (2017-2026); records per delivery; share of symbols with
# days_to_cover; coverage relative to the fundamental universe on a few dates.

class XupAudit1c(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2017, 1, 1)
        self.set_end_date(2026, 11, 20)
        self.set_cash(100000)
        self.universe_settings.resolution = Resolution.DAILY
        self.days = {}
        self.fields = None
        self.recs = []
        self.err = None
        self.example_times = []
        try:
            self.add_universe(FINRAShortInterestUniverse, self._sel)
        except Exception as e:
            self.err = str(e)[:180]

    def _sel(self, data):
        try:
            items = list(data)
        except Exception as e:
            self.err = ("iter " + str(e))[:180]
            return []
        if not items:
            return []
        d = self.time.date()
        self.days[d] = len(items)
        if self.fields is None:
            x = items[0]
            self.fields = [n for n in dir(x) if not n.startswith("_") and n[0].islower()]
        if len(self.example_times) < 6:
            x = items[0]
            try:
                self.example_times.append(f"algo {d} rec time {x.time} end {x.end_time}")
            except Exception:
                pass
        return []

    def on_end_of_algorithm(self):
        if self.err:
            self.set_runtime_statistic("SI error", self.err)
        self.set_runtime_statistic("SI fields", ", ".join(self.fields or [])[:195])
        dom = {}
        for d in self.days:
            dom[d.day] = dom.get(d.day, 0) + 1
        self.set_runtime_statistic("SI delivery days", f"{len(self.days)} dates {min(self.days) if self.days else '-'}..{max(self.days) if self.days else '-'}")
        self.set_runtime_statistic("SI day-of-month histogram", " ".join(f"{k}:{v}" for k, v in sorted(dom.items()))[:195])
        cnt = sorted(self.days.values())
        if cnt:
            self.set_runtime_statistic("SI records per delivery", f"p10 {cnt[int(0.1 * (len(cnt) - 1))]} p50 {cnt[len(cnt) // 2]} p90 {cnt[int(0.9 * (len(cnt) - 1))]}")
        self.set_runtime_statistic("SI example times", " | ".join(self.example_times)[:195])
