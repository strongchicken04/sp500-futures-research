# region imports
from AlgorithmImports import *
# endregion
#
# EXTREME-UPSIDE RESEARCH - STAGE 1d AUDIT: when do FINRA short-interest VALUES change? (owner 2026-11-24)
# Stage 1c: the FINRAShortInterestUniverse arrives every calendar day (a forward-filled snapshot, 9-18k symbols),
# so delivery dates say nothing about publication. Here: full list of data fields (properties only), any date-like
# fields, and the day-of-month histogram of the dates on which a symbol's short-interest value CHANGES (first 600
# symbols seen, 2018-2026). FINRA settlement dates are mid-month and month-end; publication is ~7-8 business
# days later (~9th and ~24th). Changes clustering at ~15th / ~month-end = settlement-stamped (look-ahead if
# unshifted); at ~9th / ~24th = publication-stamped. Aggregates only.

class XupAudit1d(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2018, 1, 1)
        self.set_end_date(2026, 11, 20)
        self.set_cash(100000)
        self.universe_settings.resolution = Resolution.DAILY
        self.track = {}
        self.last = {}
        self.changes = {}
        self.props = None
        self.datefields = {}
        self.add_universe(FINRAShortInterestUniverse, self._sel)

    def _val(self, x):
        out = []
        for n in self.vfields:
            try:
                out.append(float(getattr(x, n)))
            except Exception:
                out.append(None)
        return tuple(out)

    def _sel(self, data):
        items = list(data)
        if not items:
            return []
        if self.props is None:
            x = items[0]
            skip = ("get_", "set_", "add", "clone", "equals", "finalize", "deserialize", "reader", "get_source", "to_string", "is_sparse", "requires", "default", "supported", "data_time_zone", "data_type", "memberwise", "reference", "is_fill", "update", "filtered", "get_hash")
            self.props = [n for n in dir(x) if not n.startswith("_") and n[0].islower() and not any(n.startswith(s) for s in skip)]
            self.vfields = []
            for n in self.props:
                try:
                    v = getattr(x, n)
                    if callable(v):
                        continue
                    if isinstance(v, (int, float)) or type(v).__name__ in ("Decimal", "Int64", "Int32", "Double"):
                        self.vfields.append(n)
                    elif "date" in n.lower() or type(v).__name__ in ("datetime", "DateTime"):
                        self.datefields[n] = str(v)
                except Exception:
                    pass
        d = self.time.date()
        for x in items:
            sid = str(x.symbol.id)
            if sid not in self.track:
                if len(self.track) >= 600:
                    continue
                self.track[sid] = True
            v = self._val(x)
            if sid in self.last and v != self.last[sid]:
                self.changes[d.day] = self.changes.get(d.day, 0) + 1
                wd = d.weekday()
                self.changes[("wd", wd)] = self.changes.get(("wd", wd), 0) + 1
            self.last[sid] = v
        return []

    def on_end_of_algorithm(self):
        self.set_runtime_statistic("SI props", ", ".join(self.props or [])[:195])
        self.set_runtime_statistic("SI value fields", ", ".join(getattr(self, "vfields", []))[:195])
        self.set_runtime_statistic("SI date fields", " | ".join(f"{k}={v}" for k, v in self.datefields.items())[:195])
        dom = {k: v for k, v in self.changes.items() if isinstance(k, int)}
        tot = max(1, sum(dom.values()))
        self.set_runtime_statistic("SI change day-of-month %", " ".join(f"{k}:{v * 100.0 / tot:.0f}" for k, v in sorted(dom.items()))[:195])
        wd = {k[1]: v for k, v in self.changes.items() if isinstance(k, tuple)}
        self.set_runtime_statistic("SI change weekday", " ".join(f"{['Mo','Tu','We','Th','Fr','Sa','Su'][k]}:{v}" for k, v in sorted(wd.items())) + f" | total changes {tot} symbols {len(self.track)}")
