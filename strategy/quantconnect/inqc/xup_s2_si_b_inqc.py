# region imports
from AlgorithmImports import *
from datetime import date as _date, timedelta
import bisect
# endregion
#
# EXTREME-UPSIDE RESEARCH - STAGE 2 VALIDATION 4b: OFF-CYCLE SHORT-INTEREST CHANGES (owner 2026-11-24). Aggregates.
# Validation 4 (v2): the main cycle changes become usable 1-2 trading days after the FINRA rule publication date
# (never before), but ~45% of value changes happen on other days, spread evenly. Here, per tracked symbol (first
# 4,000 + GME AMC AAPL TSLA BBBY): duplicate records of the same symbol within one daily file; changes classified
# on-cycle (usable 0..3 trading days after a rule publication) vs off-cycle; off-cycle "flip-backs" (new value
# equals the value before the previous change -> two records alternating); share of symbols with any off-cycle
# change; the symbols with most off-cycle changes; off-cycle changes per year.

TRACK_EXTRA = ("GME", "AMC", "AAPL", "TSLA", "BBBY")


class XupS2SIb(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2018, 1, 1)
        self.set_end_date(2026, 11, 20)
        self.set_cash(100000)
        self.spy = self.add_equity("SPY", Resolution.DAILY).symbol
        self.universe_settings.resolution = Resolution.DAILY
        self.add_universe(FINRAShortInterestUniverse, self._sel)
        self.track = {}
        self.ev = {}          # sid -> list of (date, flipback)
        self.state = {}       # sid -> (current, previous distinct)
        self.dup_days = 0
        self.dup_recs = 0
        self.days = 0

    def _sel(self, data):
        d = self.time.date()
        self.days += 1
        seen = set()
        for x in data:
            sid = str(x.symbol.id)
            if sid not in self.track:
                if len(self.track) < 4000 or x.symbol.value in TRACK_EXTRA:
                    self.track[sid] = x.symbol.value
                else:
                    continue
            if sid in seen:
                self.dup_recs += 1
            seen.add(sid)
            try:
                si = float(x.short_interest)
            except Exception:
                continue
            st = self.state.get(sid)
            if st is None:
                self.state[sid] = (si, None)
                continue
            if si != st[0]:
                self.ev.setdefault(sid, []).append((d, si == st[1]))
                self.state[sid] = (si, st[0])
        return []

    def on_end_of_algorithm(self):
        S = self.set_runtime_statistic
        h = self.history(self.spy, datetime(2017, 11, 1), datetime(2026, 11, 21), Resolution.DAILY)
        td = sorted(set((ix[1] if isinstance(ix, tuple) else ix).date() if (ix[1] if isinstance(ix, tuple) else ix).hour >= 9
                        else ((ix[1] if isinstance(ix, tuple) else ix) - timedelta(days=1)).date() for ix in h.index))
        tdi = {d: i for i, d in enumerate(td)}

        def prev_td(d):
            i = bisect.bisect_right(td, d) - 1
            return td[i] if i >= 0 else d
        settle = []
        y, m = 2017, 11
        while (y, m) <= (2026, 10):
            nm = _date(y + (m == 12), m % 12 + 1, 1)
            settle += [prev_td(_date(y, m, 15)), prev_td(nm - timedelta(days=1))]
            y, m = nm.year, nm.month
        pub = sorted(td[tdi[x] + 7] for x in settle if x in tdi and tdi[x] + 7 < len(td))
        on, off, offflip, sym_off = 0, 0, 0, 0
        per_sym = []
        per_year = {}
        for sid, evs in self.ev.items():
            o = 0
            for d, fb in evs:
                i = bisect.bisect_left(td, d)
                if i >= len(td):
                    continue
                U = td[i]
                j = bisect.bisect_right(pub, U) - 1
                n = tdi[U] - tdi[pub[j]] if j >= 0 else 99
                if 0 <= n <= 3:
                    on += 1
                else:
                    off += 1
                    o += 1
                    per_year[d.year] = per_year.get(d.year, 0) + 1
                    if fb:
                        offflip += 1
            if o:
                sym_off += 1
            per_sym.append((o, self.track.get(sid, "?"), len(evs)))
        per_sym.sort(reverse=True)
        n_sym = max(1, len(self.ev))
        conc = sum(v[0] for v in per_sym[:int(0.05 * len(per_sym)) + 1])
        S("SIb on/off cycle", f"changes on-cycle {on} off-cycle {off} ({100.0 * off / max(1, on + off):.0f}%) | off-cycle flip-backs {100.0 * offflip / max(1, off):.0f}% | symbols with any off-cycle change {100.0 * sym_off / n_sym:.0f}% of {len(self.ev)} | top 5% symbols hold {100.0 * conc / max(1, off):.0f}% of off-cycle")
        S("SIb duplicates", f"duplicate records of a symbol within one day: {self.dup_recs} over {self.days} days")
        S("SIb top off-cycle symbols", " ".join(f"{t}:{o}/{n}" for o, t, n in per_sym[:12])[:198])
        S("SIb off-cycle per year", " ".join(f"{k}:{v}" for k, v in sorted(per_year.items())))
        ex = {self.track[s]: s for s in self.ev if self.track.get(s) in TRACK_EXTRA}
        S("SIb extra symbols off-cycle", " ".join(f"{t}:{next((v[0] for v in per_sym if v[1] == t), 0)}" for t in TRACK_EXTRA))
