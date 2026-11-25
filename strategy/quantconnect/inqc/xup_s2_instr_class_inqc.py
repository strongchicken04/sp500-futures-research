# region imports
from AlgorithmImports import *
from datetime import date as _date, datetime as _dt, timedelta
from collections import deque
import hashlib, random, re
from xup_ic_0 import DATA as _d0
from xup_ic_1 import DATA as _d1
from xup_ic_2 import DATA as _d2
from xup_ic_3 import DATA as _d3
# endregion
#
# EXTREME-UPSIDE RESEARCH - STAGE 2, OPTION A (owner decision 2026-11-25): HISTORICAL INSTRUMENT CLASSIFICATION
# of the broad QC US equity universe, without requiring Morningstar fundamentals. Aggregates + ticker examples only.
# Imported classification (project files xup_ic_0..3.py, plain text; Object Store reads are not permitted for
# this account and project files are limited to 32k characters) - built by
# research/extreme_upside/instrument_class/build_instrument_class.py):
#   SEC-SC  '40-Act open-end ETF share-class tickers by year 2010-2026 (effective first year - 1 .. last year)
#   NASDAQTRADER / SEC-CTE  current instrument types (ETF / ETN / CEF / PREFERRED / DEBT / WARRANT / RIGHT / UNIT /
#           ADR / COMMON / TEST / OTHER), applied to the security id holding the ticker on the latest dates
# Security-level classification (QC security id = one instrument through ticker changes), precedence:
#   1 TEST            exchange test symbols (current test-issue list + fixed list + Z?ZZT pattern)
#   2 Morningstar     has fundamentals: COMMON / COMMON_SECONDARY (non-primary US class with a primary sibling) /
#                     ADR_FOREIGN (non-primary, company country not USA) / CEF (sub-type) / PREF_OTHER (type not
#                     common); OTCM and SPAC kept as flags
#   3 SEC-SC ETF      a ticker span of the security overlaps an ETF effective range
#   4 current list    the security holds the ticker on/after 2025-06-01
#   5 ticker rules    5-letter Nasdaq suffix W / R / U / N-O-P-M / Y / F / A-B, NYSE-style .WS .U .R .RT
#   6 UNRESOLVED      no reliable evidence (kept in A, flagged; A-strict excludes it)
# A (broad price/volume, main) = COMMON + COMMON_SECONDARY + COMMON_NOFUND + ADR_FOREIGN + UNRESOLVED;
# B = securities with Morningstar fundamentals of common type.
# Outputs: class counts, coverage by year / exchange, event-universe size (+50%/5d, +100%/10d, +200%/20d
# close-based adjusted episodes) A vs B, survivorship of the classification (dead vs alive securities),
# random-date class counts and ticker samples for manual inspection, conflicts with Morningstar.

KEY = "xup/instrument_class_v1.psv"
TESTS = {"ZVZZT", "ZWZZT", "ZXZZT", "ZJZZT", "ZBZZT", "ZAZZT", "ZCZZT", "ZVV", "ZBZX", "CBO", "CBX", "ZXYZ.A", "NTEST", "ATEST", "CTEST", "MTEST", "PTEST", "ZTEST", "ZZK", "ZZZ"}
MAJOR = ("NAS", "NYS", "NYSE", "ASE", "AMEX")
LAB = ((5, 1.5), (10, 2.0), (20, 3.0))
BLK = [(2006, 2009), (2010, 2014), (2015, 2019), (2020, 2022), (2023, 2026)]
ACLASSES = ("COMMON", "COMMON_SECONDARY", "COMMON_NOFUND", "ADR_FOREIGN", "UNRESOLVED")
DATA_END = _date(2026, 8, 27)


class XupS2InstrClass(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2006, 1, 1)
        self.set_end_date(2026, 11, 20)
        self.set_cash(100000)
        self.universe_settings.resolution = Resolution.DAILY
        self.err = []
        self.sec_etf = {}
        self.cur = {}
        self.nrows = 0
        try:
            for ln in (_d0 + "\n" + _d1 + "\n" + _d2 + "\n" + _d3).split("\n"):
                p = ln.split(" ")
                if len(p) < 4:
                    continue
                tks = p[3].split(",")
                self.nrows += len(tks)
                if p[0] == "E":
                    rng = (_date(int(p[1]), 1, 1), _date(int(p[2]), 12, 31))
                    for tk in tks:
                        self.sec_etf.setdefault(tk, []).append(rng)
                else:
                    typ, ex = p[1], p[2]
                    for tk in tks:
                        if tk in self.cur and ex == "SECCTE":
                            continue
                        self.cur[tk] = (typ, ex, "CTE" if ex == "SECCTE" else "NAS")
                        if typ == "TEST":
                            TESTS.add(tk)
        except Exception as e:
            self.err.append("import " + str(e)[:120])
        self.add_universe(self._select)
        self.span = {}      # sid -> list [ticker, first, last]
        self.first = {}
        self.last = {}
        self.ms = {}        # sid -> dict of Morningstar evidence counts
        self.msex = {}
        self.hist = {}
        self.lastev = {}
        self.ev = {}        # sid -> [e5, e10, e20, {block: e10}]
        self.day = 0
        self.cm = None
        rng = random.Random(77)
        self.rdates = sorted(_date(a, 1, 1) + timedelta(days=rng.randint(0, (min(_date(b, 12, 31), _date(2026, 8, 1)) - _date(a, 1, 1)).days)) for a, b in BLK)
        self.rpend = list(self.rdates)
        self.rsets = {}

    def _g(self, fn, default=None):
        try:
            return fn()
        except Exception:
            return default

    def _ms_month(self, fundamental, d):
        prim_by_co = {}
        rows = []
        for x in fundamental:
            if not x.has_fundamental_data:
                continue
            sid = str(x.symbol.id)
            sr = self._g(lambda: x.security_reference)
            if sr is None:
                continue
            typ = self._g(lambda: str(sr.security_type), "")
            sub = self._g(lambda: str(sr.common_share_sub_type), "").lower()
            pr = self._g(lambda: sr.is_primary_share, None)
            co = self._g(lambda: str(x.company_reference.company_id), "?")
            ctry = self._g(lambda: str(x.company_reference.country_id), "?")
            ex = self._g(lambda: str(sr.exchange_id), "?")
            nm = self._g(lambda: str(x.company_reference.standard_name), "") or ""
            spac = "acquisition" in nm.lower() and 9.0 <= float(x.price) <= 10.8
            if typ == "ST00000001" and pr is not False:
                prim_by_co[co] = 1
            rows.append((sid, typ, sub, pr, co, ctry, ex, spac))
        for sid, typ, sub, pr, co, ctry, ex, spac in rows:
            if typ != "ST00000001":
                c = "PREF_OTHER"
            elif "closed" in sub:
                c = "CEF"
            elif pr is False and ctry != "USA":
                c = "ADR_FOREIGN"
            elif pr is False and prim_by_co.get(co):
                c = "COMMON_SECONDARY"
            else:
                c = "COMMON"
            m = self.ms.setdefault(sid, {})
            m[c] = m.get(c, 0) + 1
            if spac:
                m["spac"] = m.get("spac", 0) + 1
            self.msex[sid] = ex

    def _select(self, fundamental):
        d = self.time.date()
        self.day += 1
        mkey = (d.year, d.month)
        if mkey != self.cm:
            self.cm = mkey
            self._ms_month(fundamental, d)
        isrand = bool(self.rpend) and d >= self.rpend[0]
        if isrand:
            self.rpend.pop(0)
            rs = self.rsets[d] = []
        b = next(i for i, (a, z) in enumerate(BLK) if a <= d.year <= z)
        for x in fundamental:
            sid = str(x.symbol.id)
            tk = x.symbol.value
            sp = self.span.get(sid)
            if sp is None:
                self.span[sid] = [[tk, d, d]]
                self.first[sid] = d
            elif sp[-1][0] != tk:
                sp.append([tk, d, d])
            else:
                sp[-1][2] = d
            self.last[sid] = d
            px = float(x.price)
            vol = float(x.volume)
            adj = self._g(lambda: float(x.adjusted_price), px)
            if isrand and px > 0 and vol > 0:
                rs.append(sid)
            h = self.hist.get(sid)
            if h is None:
                h = deque(maxlen=21)
                self.hist[sid] = h
            h.append((adj, vol))
            n = len(h)
            if n < 6:
                continue
            hl = None
            for k, (hz, mult) in enumerate(LAB):
                if n < hz + 1:
                    break
                st = h[-1 - hz]
                if st[0] <= 0 or st[1] <= 0:
                    continue
                if hl is None:
                    hl = [r[0] for r in h]
                if max(hl[-hz:]) < mult * st[0]:
                    continue
                lk = (k, sid)
                si = self.day - hz
                if lk not in self.lastev or si - self.lastev[lk] >= hz:
                    self.lastev[lk] = si
                    e = self.ev.get(sid)
                    if e is None:
                        e = self.ev[sid] = [0, 0, 0, {}]
                    e[k] += 1
                    if k == 1:
                        e[3][b] = e[3].get(b, 0) + 1
        return []

    # ---------------- classification ----------------
    def _rule(self, tk):
        if re.fullmatch(r"Z[A-Z]ZZT", tk) or tk in TESTS:
            return "TEST"
        if tk.endswith(".WS") or ".WS." in tk or tk.endswith(".W"):
            return "WARRANT"
        if tk.endswith(".U") or tk.endswith(".UN"):
            return "UNIT"
        if tk.endswith(".R") or tk.endswith(".RT"):
            return "RIGHT"
        if re.fullmatch(r"[A-Z]{4}[A-Z]", tk):
            s = tk[-1]
            return {"W": "WARRANT", "R": "RIGHT", "U": "UNIT", "P": "PREFERRED", "O": "PREFERRED", "N": "PREFERRED", "M": "PREFERRED",
                    "Y": "ADR_FOREIGN", "F": "ADR_FOREIGN", "A": "COMMON_NOFUND", "B": "COMMON_NOFUND", "Q": "COMMON_NOFUND"}.get(s)
        return None

    def _classify(self, sid):
        spans = self.span[sid]
        tks = [s[0] for s in spans]
        if any(self._rule(t) == "TEST" for t in tks):
            return "TEST", "test"
        m = self.ms.get(sid)
        if m:
            c = max((k for k in m if k != "spac"), key=lambda k: m[k])
            return c, "ms"
        for t, a, z in spans:
            for st, en in self.sec_etf.get(t, []):
                if a <= en and z >= st:
                    return "ETF", "sec"
        if self.last[sid] >= _date(2025, 6, 1):
            t = spans[-1][0]
            if t in self.cur:
                typ = self.cur[t][0]
                typ = {"COMMON": "COMMON_NOFUND", "ADR": "ADR_FOREIGN", "OTHER": "UNRESOLVED"}.get(typ, typ)
                return typ, "cur"
        for t in reversed(tks):
            r = self._rule(t)
            if r:
                return r, "rule"
        return "UNRESOLVED", "none"

    def on_end_of_algorithm(self):
        S = self.set_runtime_statistic
        if self.err:
            S("ERR", " | ".join(self.err)[:198])
        cls, src = {}, {}
        for sid in self.span:
            c, s = self._classify(sid)
            cls[sid] = c
            src[sid] = s
        allc = ["COMMON", "COMMON_SECONDARY", "COMMON_NOFUND", "ADR_FOREIGN", "UNRESOLVED", "ETF", "ETN", "CEF", "PREFERRED", "PREF_OTHER", "DEBT", "WARRANT", "RIGHT", "UNIT", "TEST"]
        tot = {c: 0 for c in allc}
        nof = {c: 0 for c in allc}
        for sid, c in cls.items():
            tot[c] = tot.get(c, 0) + 1
            if src[sid] != "ms" and src[sid] != "test":
                nof[c] = nof.get(c, 0) + 1
        nfund = sum(1 for s in cls if src[s] == "ms")
        S("C0 import", f"rows {self.nrows} SEC-ETF tickers {len(self.sec_etf)} current tickers {len(self.cur)} | securities seen {len(cls)} with fundamentals {nfund} without {len(cls) - nfund}")
        S("C1 all securities by class", " ".join(f"{c} {tot.get(c, 0)}" for c in allc)[:198])
        S("C2 no-fundamental by class", " ".join(f"{c} {nof.get(c, 0)}" for c in allc if nof.get(c, 0))[:198])
        sc = {}
        for sid, c in cls.items():
            k = (src[sid], c)
            sc[k] = sc.get(k, 0) + 1
        S("C3 evidence source", " ".join(f"{s}:{c} {v}" for (s, c), v in sorted(sc.items(), key=lambda kv: -kv[1])[:14])[:198])
        # conflicts: Morningstar-covered securities that the import calls a fund / note
        conf = {}
        confex = {}
        for sid in self.ms:
            for t, a, z in self.span.get(sid, []):
                ext = None
                if any(a <= en and z >= st for st, en in self.sec_etf.get(t, [])):
                    ext = "ETF"
                elif self.last[sid] >= _date(2025, 6, 1) and t == self.span[sid][-1][0] and t in self.cur and self.cur[t][0] in ("ETF", "ETN", "CEF", "PREFERRED", "DEBT", "WARRANT", "UNIT", "RIGHT"):
                    ext = self.cur[t][0]
                if ext:
                    k = (cls[sid], ext)
                    conf[k] = conf.get(k, 0) + 1
                    if cls[sid] == "COMMON" and len(confex.setdefault(ext, [])) < 6:
                        confex[ext].append(f"{t}{str(a.year)[2:]}")
                    break
        S("C4 Morningstar vs import conflicts", " ".join(f"MS {a} / import {b}: {v}" for (a, b), v in sorted(conf.items(), key=lambda kv: -kv[1])[:6])[:198] or "none")
        S("C5 MS COMMON but import fund/other: examples", " | ".join(f"{k}: {' '.join(v)}" for k, v in confex.items())[:198] or "none")
        # coverage by year (securities active at any time in the year)
        yrs = {}
        for sid, c in cls.items():
            for y in range(self.first[sid].year, self.last[sid].year + 1):
                dct = yrs.setdefault(y, {})
                dct[c] = dct.get(c, 0) + 1
                if c in ACLASSES:
                    dct["A"] = dct.get("A", 0) + 1
                    if src[sid] == "ms":
                        dct["Af"] = dct.get("Af", 0) + 1
        ys = sorted(yrs)
        for j in range(0, len(ys), 4):
            parts = []
            for y in ys[j:j + 4]:
                v = yrs[y]
                fund_k = v.get("Af", 0)
                parts.append(f"{y}: A {v.get('A', 0)} (fund {fund_k} nofund {v.get('A', 0) - fund_k} unres {v.get('UNRESOLVED', 0)}) ETF {v.get('ETF', 0)} ETN {v.get('ETN', 0)} CEF {v.get('CEF', 0)}")
            S(f"Y{j // 4} coverage by year", " | ".join(parts)[:198])
        # exchange coverage of A
        exc = {}
        for sid, c in cls.items():
            if c not in ACLASSES:
                continue
            if src[sid] == "ms":
                e = self.msex.get(sid, "?")
            elif src[sid] == "cur":
                e = self.cur.get(self.span[sid][-1][0], ("", "?"))[1] or "?"
            else:
                e = "unknown"
            exc[e] = exc.get(e, 0) + 1
        S("X A by exchange", " ".join(f"{k} {v}" for k, v in sorted(exc.items(), key=lambda kv: -kv[1])[:10])[:198])
        # events
        for k, (hz, mult) in enumerate(LAB):
            ec = {}
            for sid, e in self.ev.items():
                ec[cls[sid]] = ec.get(cls[sid], 0) + e[k]
            a = sum(ec.get(c, 0) for c in ACLASSES)
            bonly = sum(e[k] for sid, e in self.ev.items() if src[sid] == "ms" and cls[sid] == "COMMON")
            S(f"E +{int((mult - 1) * 100)}%/{hz}d episodes", (f"A {a} (A-strict {a - ec.get('UNRESOLVED', 0)}) vs fundamental COMMON {bonly} ({100.0 * (a / max(1, bonly) - 1):+.0f}%) | " + " ".join(f"{c} {ec.get(c, 0)}" for c in allc if ec.get(c, 0)))[:198])
        bl = []
        for bi, (a0, z0) in enumerate(BLK):
            a = sum(e[3].get(bi, 0) for sid, e in self.ev.items() if cls[sid] in ACLASSES)
            u = sum(e[3].get(bi, 0) for sid, e in self.ev.items() if cls[sid] == "UNRESOLVED")
            bo = sum(e[3].get(bi, 0) for sid, e in self.ev.items() if src[sid] == "ms" and cls[sid] == "COMMON")
            bl.append(f"{a0}-{z0 % 100:02d} A {a} unres {u} B {bo}")
        S("E +100%/10d by block", " | ".join(bl))
        # survivorship of the classification: no-fundamental securities, dead vs alive, by first-seen block
        sv = {}
        for sid, c in cls.items():
            if src[sid] in ("ms", "test"):
                continue
            dead = self.last[sid] < _date(2026, 6, 1)
            fb = next(i for i, (a0, z0) in enumerate(BLK) if a0 <= self.first[sid].year <= z0)
            k = (dead, fb)
            v = sv.setdefault(k, [0, 0, 0])
            v[0] += 1
            if c != "UNRESOLVED":
                v[1] += 1
            if c in ("ETF", "ETN", "CEF"):
                v[2] += 1
        for dead in (False, True):
            S(f"V no-fund {'DEAD' if dead else 'ALIVE'} resolved/fund share by first block", " | ".join(f"{BLK[fb][0]}: n {sv.get((dead, fb), [0, 0, 0])[0]} res {100.0 * sv.get((dead, fb), [0, 1, 0])[1] / max(1, sv.get((dead, fb), [1])[0]):.0f}% fund {100.0 * sv.get((dead, fb), [0, 0, 0])[2] / max(1, sv.get((dead, fb), [1])[0]):.0f}%" for fb in range(5))[:198])
        # random dates: counts and samples
        for d in sorted(self.rsets):
            ids = self.rsets[d]
            cc = {}
            for sid in ids:
                cc[cls[sid]] = cc.get(cls[sid], 0) + 1
            S(f"R {d} counts", " ".join(f"{c} {cc.get(c, 0)}" for c in allc if cc.get(c, 0))[:198])

            def tick_on(sid):
                for t, a, z in self.span[sid]:
                    if a <= d <= z:
                        return t
                return self.span[sid][-1][0]
            samp = []
            for c, k in (("ETF", 4), ("ETN", 2), ("CEF", 2), ("PREFERRED", 2), ("WARRANT", 2), ("UNIT", 1), ("COMMON_NOFUND", 4), ("ADR_FOREIGN", 2), ("UNRESOLVED", 8)):
                pool = sorted([s for s in ids if cls[s] == c], key=lambda s: hashlib.md5((s + str(d)).encode()).hexdigest())[:k]
                if pool:
                    samp.append(c[:4] + ":" + ",".join(tick_on(s) for s in pool))
            S(f"R {d} samples", " ".join(samp)[:198])
        # unresolved securities with events (hash sample) and overall unresolved sample
        ue = sorted([s for s in cls if cls[s] == "UNRESOLVED" and s in self.ev and self.ev[s][1] > 0], key=lambda s: hashlib.md5(s.encode()).hexdigest())[:40]
        txt = " ".join(f"{self.span[s][-1][0]}{str(self.first[s].year)[2:]}" for s in ue)
        for j in range(0, min(len(txt), 380), 190):
            S(f"U unresolved with +100/10 events {j // 190}", txt[j:j + 190])
        ua = sorted([s for s in cls if cls[s] == "UNRESOLVED"], key=lambda s: hashlib.md5(("u" + s).encode()).hexdigest())[:30]
        S("U unresolved random", " ".join(f"{self.span[s][-1][0]}{str(self.first[s].year)[2:]}-{str(self.last[s].year)[2:]}" for s in ua)[:198])
        nev = sum(1 for s in cls if cls[s] == "UNRESOLVED" and s in self.ev)
        S("U unresolved totals", f"securities {tot.get('UNRESOLVED', 0)} with any event {nev} | median life days {sorted((self.last[s] - self.first[s]).days for s in cls if cls[s] == 'UNRESOLVED')[tot.get('UNRESOLVED', 1) // 2] if tot.get('UNRESOLVED', 0) else 0}")
