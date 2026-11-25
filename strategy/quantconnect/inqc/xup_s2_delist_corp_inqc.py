# region imports
from AlgorithmImports import *
from datetime import date as _date, timedelta
# endregion
#
# EXTREME-UPSIDE RESEARCH - STAGE 2 VALIDATION 2: DELISTINGS / BANKRUPTCIES AND CORPORATE ACTIONS
# (owner 2026-11-24). Runs INSIDE QuantConnect; aggregates / a few summary numbers per named security only.
# Securities are captured from the Fundamental universe on a date BEFORE their event (so the point-in-time symbol
# is used, not today's owner of the ticker), kept subscribed (RAW normalisation), and every Split / Dividend /
# Delisting / SymbolChanged event that LEAN emits in on_data is recorded with its timestamp.
# v2: history fill_forward=False; window anchored on the delisting event when no bar was recorded.
#   DL  LEH WM CIT RSH SHLD HTZ BBBY SIVB FRC: company name, last bar date, last raw close and adjusted close,
#       gap before the last bar, LEAN delisting events (warning / delisted, timestamp, price), Morningstar
#       delisting_date / delisting_reason (current snapshot, look-ahead field - used here only for validation)
#   CA  AAPL TSLA NVDA AMZN GOOGL (forward splits), GE (1:8 reverse), MULN SNDL AMC NKLA (low-priced reverse
#       splits), COST (special dividends): for every split event the raw and adjusted close ratio across the
#       ex-date, raw vs adjusted 10-session max-close and max-high excursion from the pre-split close, whether a
#       +50% "event" would be created on raw or adjusted data, and the timestamps of the split event vs the first
#       post-split bar; special dividends: distribution / reference price and adjusted vs raw step
#   DR  Morningstar delisting_reason distribution among securities present each January (what reasons exist)

CAPTURE = {"LEH": _date(2008, 6, 2), "WM": _date(2008, 6, 2), "CIT": _date(2009, 6, 1), "RSH": _date(2014, 6, 2),
           "SHLD": _date(2018, 6, 1), "HTZ": _date(2020, 3, 2), "BBBY": _date(2023, 1, 3), "SIVB": _date(2023, 2, 1),
           "FRC": _date(2023, 3, 1), "AAPL": _date(2020, 8, 3), "TSLA": _date(2020, 8, 3), "NVDA": _date(2021, 7, 1),
           "AMZN": _date(2022, 5, 2), "GOOGL": _date(2022, 7, 1), "GE": _date(2021, 7, 1), "MULN": _date(2023, 4, 3),
           "SNDL": _date(2022, 6, 1), "AMC": _date(2023, 8, 1), "NKLA": _date(2024, 6, 3), "COST": _date(2020, 11, 2)}
DELISTED = ("LEH", "WM", "CIT", "RSH", "SHLD", "HTZ", "BBBY", "SIVB", "FRC")


class XupS2DelistCorp(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2008, 1, 1)
        self.set_end_date(2024, 12, 31)
        self.set_cash(100000)
        self.universe_settings.resolution = Resolution.DAILY
        self.universe_settings.data_normalization_mode = DataNormalizationMode.RAW
        self.universe_settings.fill_forward = False
        self.add_universe(self._select)
        self.sym = {}        # ticker -> Symbol
        self.info = {}       # ticker -> dict
        self.events = {}     # ticker -> list of strings
        self.splits = {}     # ticker -> list of (date, factor, ref)
        self.divs = {}       # ticker -> list of (date, dist, ref)
        self.lastbar = {}    # ticker -> (date, close, prev date)
        self.dlt = {}        # ticker -> last delisting event time
        self.dr = {}
        self.dr_years = set()
        self.err = []

    def _g(self, fn, default=None):
        try:
            return fn()
        except Exception:
            return default

    def _select(self, fundamental):
        d = self.time.date()
        want = [tk for tk, cd in CAPTURE.items() if tk not in self.sym and d >= cd]
        dr = d.month == 1 and d.year not in self.dr_years
        if want or dr:
            for x in fundamental:
                if dr and x.has_fundamental_data:
                    r = self._g(lambda: str(x.security_reference.delisting_reason), "?")
                    dd = self._g(lambda: x.security_reference.delisting_date, None)
                    if dd is not None and self._g(lambda: dd.year, 9999) < 2100:
                        self.dr[r] = self.dr.get(r, 0) + 1
                    else:
                        self.dr["(none)"] = self.dr.get("(none)", 0) + 1
                if want and x.symbol.value in want:
                    tk = x.symbol.value
                    self.sym[tk] = x.symbol
                    self.info[tk] = {
                        "name": self._g(lambda: str(x.company_reference.standard_name), "?"),
                        "dd": self._g(lambda: str(x.security_reference.delisting_date)[:10], "?"),
                        "dr": self._g(lambda: str(x.security_reference.delisting_reason), "?"),
                        "cap": str(d), "px": float(x.price)}
            if dr:
                self.dr_years.add(d.year)
        return list(self.sym.values())

    def _tk(self, symbol):
        for tk, s in self.sym.items():
            if s == symbol:
                return tk
        return None

    def on_data(self, data):
        d = self.time.date()
        for kv in data.splits:
            sp = kv.value
            tk = self._tk(kv.key)
            if tk:
                t = int(sp.type)
                self.events.setdefault(tk, []).append(f"S{t}@{sp.time.strftime('%y%m%d-%H%M')} f{float(sp.split_factor):.4g} ref{float(sp.reference_price):.4g}")
                if t == 1:
                    self.splits.setdefault(tk, []).append((sp.time, float(sp.split_factor), float(sp.reference_price)))
        for kv in data.dividends:
            dv = kv.value
            tk = self._tk(kv.key)
            if tk:
                self.divs.setdefault(tk, []).append((dv.time, float(dv.distribution), float(dv.reference_price)))
        for kv in data.delistings:
            dl = kv.value
            tk = self._tk(kv.key)
            if tk:
                self.dlt[tk] = dl.time
                self.events.setdefault(tk, []).append(f"D{int(dl.type)}@{dl.time.strftime('%y%m%d-%H%M')} px{float(dl.price):.4g}")
        for kv in data.symbol_changed_events:
            ev = kv.value
            tk = self._tk(kv.key)
            if tk:
                self.events.setdefault(tk, []).append(f"chg {ev.old_symbol}->{ev.new_symbol}@{ev.time.strftime('%y%m%d')}")
        for kv in data.bars:
            tk = self._tk(kv.key)
            if tk:
                prev = self.lastbar.get(tk)
                self.lastbar[tk] = (kv.value.end_time, float(kv.value.close), prev[0] if prev else None)

    def _hist(self, s, a, b, mode):
        h = self.history(s, a, b, Resolution.DAILY, fill_forward=False, data_normalization_mode=mode)
        if h is None or h.empty:
            return []
        out = []
        for ix, r in h.iterrows():
            t = ix[1] if isinstance(ix, tuple) else ix
            out.append((t, float(r["open"]), float(r["high"]), float(r["close"]), float(r["volume"]) if "volume" in r else 0.0))
        return out

    def on_end_of_algorithm(self):
        S = self.set_runtime_statistic
        for tk in DELISTED:
            s = self.sym.get(tk)
            if s is None:
                S(f"DL {tk}", "not captured")
                continue
            inf = self.info[tk]
            try:
                lb = self.lastbar.get(tk)
                end = lb[0] if lb else self.dlt.get(tk, datetime(2024, 12, 31))
                raw = self._hist(s, end - timedelta(days=45), end + timedelta(days=400), DataNormalizationMode.RAW)
                adj = self._hist(s, end - timedelta(days=45), end + timedelta(days=400), DataNormalizationMode.ADJUSTED)
                lr = raw[-1] if raw else None
                la = adj[-1] if adj else None
                gap = (raw[-1][0] - raw[-2][0]).days if len(raw) >= 2 else -1
                v5 = sum(r[4] for r in raw[-5:]) / 5 if len(raw) >= 5 else -1
                ev = " ".join(self.events.get(tk, []))[-70:]
                S(f"DL {tk}", (f"{inf['name'][:18]} | last {str(lr[0])[:10] if lr else '-'} raw {lr[3] if lr else 0:.3f} adj {la[3] if la else 0:.3f} gap {gap}d vol5 {v5 / 1e6:.1f}M"
                                f" | MS dd {inf['dd']} rsn {inf['dr'][:10]} | ev {ev}")[:198])
            except Exception as e:
                S(f"DL {tk}", f"error {str(e)[:150]}")
        for tk in ("AAPL", "TSLA", "NVDA", "AMZN", "GOOGL", "GE", "MULN", "SNDL", "AMC", "NKLA"):
            s = self.sym.get(tk)
            if s is None:
                S(f"CA {tk}", "not captured")
                continue
            parts = []
            try:
                for (t, f, ref) in self.splits.get(tk, [])[:3]:
                    raw = self._hist(s, t - timedelta(days=10), t + timedelta(days=20), DataNormalizationMode.RAW)
                    adj = self._hist(s, t - timedelta(days=10), t + timedelta(days=20), DataNormalizationMode.ADJUSTED)
                    td = t.date()
                    i0 = next((i for i, r in enumerate(raw) if r[0].date() >= td), None)
                    j0 = next((i for i, r in enumerate(adj) if r[0].date() >= td), None)
                    if i0 is None or i0 == 0 or j0 is None or j0 == 0:
                        parts.append(f"{td} f{f:.4g} nobars")
                        continue
                    rr = raw[i0][3] / raw[i0 - 1][3] - 1
                    ar = adj[j0][3] / adj[j0 - 1][3] - 1
                    rmx = max(r[3] for r in raw[i0:i0 + 10]) / raw[i0 - 1][3] - 1
                    amx = max(r[3] for r in adj[j0:j0 + 10]) / adj[j0 - 1][3] - 1
                    ahx = max(r[2] for r in adj[j0:j0 + 10]) / adj[j0 - 1][3] - 1
                    parts.append(f"{td} f{f:.4g} ref{ref:.4g} pre{raw[i0 - 1][3]:.4g} | ret raw {rr * 100:+.0f}% adj {ar * 100:+.1f}% | 10d maxC raw {rmx * 100:+.0f}% adj {amx * 100:+.0f}% maxH adj {ahx * 100:+.0f}% | bar {raw[i0][0].strftime('%m%d-%H%M')}")
                S(f"CA {tk}", (f"n{len(self.splits.get(tk, []))} " + " || ".join(parts))[:198])
            except Exception as e:
                S(f"CA {tk}", f"error {str(e)[:150]}")
        # special dividends COST
        s = self.sym.get("COST")
        if s is not None:
            try:
                big = [(t, dd, ref) for (t, dd, ref) in self.divs.get("COST", []) if ref > 0 and dd / ref > 0.01]
                parts = []
                for (t, dd, ref) in big[:2]:
                    raw = self._hist(s, t - timedelta(days=6), t + timedelta(days=3), DataNormalizationMode.RAW)
                    adj = self._hist(s, t - timedelta(days=6), t + timedelta(days=3), DataNormalizationMode.ADJUSTED)
                    td = t.date()
                    i0 = next((i for i, r in enumerate(raw) if r[0].date() >= td), None)
                    j0 = next((i for i, r in enumerate(adj) if r[0].date() >= td), None)
                    if i0 and j0:
                        parts.append(f"{td} div {dd:.2f} ref {ref:.1f} ({dd / ref * 100:.1f}%) raw {(raw[i0][3] / raw[i0 - 1][3] - 1) * 100:+.1f}% adj {(adj[j0][3] / adj[j0 - 1][3] - 1) * 100:+.1f}%")
                S("CA COST special div", (f"divs {len(self.divs.get('COST', []))} big {len(big)} | " + " || ".join(parts))[:198])
            except Exception as e:
                S("CA COST special div", f"error {str(e)[:150]}")
        # event timestamp conventions (one example)
        S("CA event log GE", " ".join(self.events.get("GE", []))[:198])
        S("CA event log MULN", " ".join(self.events.get("MULN", []))[:198])
        tot = max(1, sum(self.dr.values()))
        S("DR reasons (Jan snapshots)", " ".join(f"{k}:{v}" for k, v in sorted(self.dr.items(), key=lambda kv: -kv[1])[:10])[:198])
