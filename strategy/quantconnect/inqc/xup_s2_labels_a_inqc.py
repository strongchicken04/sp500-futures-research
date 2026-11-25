# region imports
from AlgorithmImports import *
from datetime import date as _date, timedelta
import hashlib, bisect
import numpy as np
import re
from xup_ic_0 import DATA as _d0
from xup_ic_1 import DATA as _d1
from xup_ic_2 import DATA as _d2
from xup_ic_3 import DATA as _d3
from xup_ic_4 import DATA as _d4
from numpy.lib.stride_tricks import sliding_window_view as _swv
# endregion
#
# EXTREME-UPSIDE RESEARCH - STAGE 2, OPTION A: LABEL INTEGRITY ON THE SECURITIES ADDED BY UNIVERSE A
# (owner decision 2026-11-25). Same label construction and statistics as xup_s2_labels_inqc.py (v2: fill-forward
# off), but the sample is drawn (fixed hash) from securities WITHOUT Morningstar fundamentals that the imported
# classification does not identify as ETF / ETN / CEF / preferred / debt / warrant / right / unit / test:
#   ADDED-COMMON = current list says common stock or ticker rule says class share / bankrupt common
#   ADDED-ADR    = current list says ADR or 5-letter Y/F
#   UNRESOLVED   = no evidence
# Extra check: windows crossing a gap of more than 10 market sessions (possible ticker-reuse splice) and the number
# of securities whose series contains such gaps.
EXAMPLES = [("GME", _date(2021, 1, 12)), ("GME", _date(2021, 1, 22)), ("AMC", _date(2021, 5, 21)), ("MULN", _date(2023, 5, 3)),
            ("BBBY", _date(2022, 8, 8)), ("BBBY", _date(2023, 4, 14)), ("SIVB", _date(2023, 3, 3))]
CAPTURE = {"GME": _date(2020, 12, 1), "AMC": _date(2020, 12, 1), "MULN": _date(2023, 4, 3), "BBBY": _date(2022, 7, 1), "SIVB": _date(2023, 2, 1)}
MAJOR = ("NAS", "NYS", "NYSE", "ASE", "AMEX")
HS = (5, 10, 20)
TH = (0.5, 1.0, 2.0)
SAMPLE_MOD = 4    # fixed hash over no-fundamental securities


class XupS2Labels(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2006, 1, 1)
        self.set_end_date(2026, 11, 20)
        self.set_cash(100000)
        self.universe_settings.resolution = Resolution.DAILY
        self.add_universe(self._select)
        self.sym = {}
        self.sample = {}
        self.seen = {}
        self.months = set()
        self.err = []
        self.sec_etf, self.ncen, self.cur = {}, {}, {}
        for ln in "\n".join((_d0, _d1, _d2, _d3, _d4)).split("\n"):
            p = ln.split(" ")
            if len(p) < 4:
                continue
            if p[0] == "E":
                for tk in p[3].split(","):
                    self.sec_etf.setdefault(tk, []).append((_date(int(p[1]), 1, 1), _date(int(p[2]), 12, 31)))
            elif p[0] == "K" and len(p) >= 5:
                for tk in p[4].split(","):
                    self.ncen.setdefault(tk, []).append((_date(int(p[1]), 1, 1), _date(int(p[2]), 12, 31), p[3]))
            elif p[0] == "C":
                for tk in p[3].split(","):
                    if tk in self.cur and p[2] == "SECCTE":
                        continue
                    self.cur[tk] = p[1]

    def _g(self, fn, default=None):
        try:
            return fn()
        except Exception:
            return default

    def _core(self, x):
        if not x.has_fundamental_data:
            return False
        sr = self._g(lambda: x.security_reference)
        if sr is None or self._g(lambda: str(sr.security_type), "") != "ST00000001":
            return False
        if "closed" in self._g(lambda: str(sr.common_share_sub_type), "").lower():
            return False
        if self._g(lambda: sr.is_primary_share, None) is False:
            return False
        return self._g(lambda: str(sr.exchange_id), "?") in MAJOR

    def _select(self, fundamental):
        d = self.time.date()
        mkey = (d.year, d.month)
        want = [tk for tk, cd in CAPTURE.items() if tk not in self.sym and d >= cd]
        if mkey in self.months and not want:
            return []
        monthly = mkey not in self.months
        self.months.add(mkey)
        for x in fundamental:
            if want and x.symbol.value in want:
                self.sym[x.symbol.value] = x.symbol
            if monthly and not x.has_fundamental_data:
                sid = str(x.symbol.id)
                if int(hashlib.md5(sid.encode()).hexdigest()[:8], 16) % SAMPLE_MOD != 0:
                    continue
                self.sample[sid] = x.symbol
                self.seen.setdefault(sid, []).append((x.symbol.value, d))
        return []

    def _group(self, sid):
        obs = self.seen[sid]
        tks = set(t for t, _ in obs)
        for t in tks:
            if re.fullmatch(r"Z[A-Z]ZZT", t) or t in ("ZVV", "ZBZX", "CBO", "CBX"):
                return None
            if t.endswith((".WS", ".U", ".R", ".RT", ".W")):
                return None
            if re.fullmatch(r"[A-Z]{5}", t) and t[-1] in "WRUPONM":
                return None
        for t, d in obs:
            if any(st <= d <= en for st, en in self.sec_etf.get(t, [])):
                return None
            if any(st <= d <= en for st, en, ty in self.ncen.get(t, [])):
                return None
        lt, ld = obs[-1]
        c = self.cur.get(lt) if ld >= _date(2025, 6, 1) else None
        if c is not None and c not in ("COMMON", "ADR", "OTHER"):
            return None
        if c == "COMMON" or (re.fullmatch(r"[A-Z]{5}", lt) and lt[-1] in "ABQ"):
            return "ADDED-COMMON"
        if c == "ADR" or (re.fullmatch(r"[A-Z]{5}", lt) and lt[-1] in "YF"):
            return "ADDED-ADR"
        return "UNRESOLVED"

    # ---------- helpers ----------
    def _frame(self, syms, mode):
        h = self.history(syms, datetime(2006, 1, 1), datetime(2026, 11, 21), Resolution.DAILY, fill_forward=False, data_normalization_mode=mode)
        out = {}
        if h is None or h.empty:
            return out
        for s in syms:
            try:
                df = h.loc[s]
            except Exception:
                continue
            if df is None or len(df) == 0:
                continue
            ds = [(t.date() if t.hour >= 9 else (t - timedelta(days=1)).date()) for t in df.index]
            out[s] = (ds, df["open"].values.astype(float), df["high"].values.astype(float), df["close"].values.astype(float), df["volume"].values.astype(float))
        return out

    def _ex_one(self, tk, t0):
        s = self.sym.get(tk)
        if s is None:
            return "not captured"
        adj = self._frame([s], DataNormalizationMode.ADJUSTED).get(s)
        raw = self._frame([s], DataNormalizationMode.RAW).get(s)
        if adj is None:
            return "no data"
        ds, o, hi, c, v = adj
        i = bisect.bisect_right(ds, t0) - 1
        if i < 0 or ds[i] != t0:
            return f"t not a session (nearest {ds[i] if i >= 0 else '-'})"
        n_after = len(ds) - 1 - i
        e = o[i + 1] if n_after >= 1 else float("nan")
        parts = [f"c_t {c[i]:.2f} o_t+1 {e:.2f} gap {(e / c[i] - 1) * 100:+.0f}%"]
        for hz, th in zip(HS, TH):
            if n_after >= 1:
                w = slice(i + 1, min(i + hz, len(ds) - 1) + 1)
                mh = hi[w].max() / e - 1
                comp = n_after >= hz
                cb = (c[i + hz] / e - 1) if comp else float("nan")
                parts.append(f"{hz}d A {mh * 100:+.0f}%{'Y' if mh >= th else 'n'} B {cb * 100:+.0f}%{'Y' if comp and cb >= th else ('n' if comp else '?')}{'' if comp else ' INCOMPLETE(' + str(n_after) + ')'}")
        if raw is not None:
            rd, ro, rh, rc, rv = raw
            j = bisect.bisect_right(rd, t0) - 1
            if j >= 0 and rd[j] == t0 and j + 1 < len(rd):
                rmx = rh[j + 1:j + 11].max() / ro[j + 1] - 1
                parts.append(f"RAW 10d A {rmx * 100:+.0f}%")
        parts.append(f"last {ds[-1]}")
        return " | ".join(parts)

    def _halt_proxy(self):
        s = self.sym.get("GME")
        if s is None:
            return "GME not captured"
        out = []
        for d0 in (_date(2021, 1, 27), _date(2021, 1, 28), _date(2021, 2, 1)):
            h = self.history(s, datetime(d0.year, d0.month, d0.day, 9, 30), datetime(d0.year, d0.month, d0.day, 16, 0), Resolution.MINUTE, fill_forward=False)
            n = 0 if h is None or h.empty else len(h)
            out.append(f"{d0.strftime('%m%d')} RTH bars {n}/390")
        return " | ".join(out)

    def on_end_of_algorithm(self):
        S = self.set_runtime_statistic
        # market sessions (for missing-session detection)
        try:
            spy = self.add_equity("SPY", Resolution.DAILY).symbol
            sp = self._frame([spy], DataNormalizationMode.RAW).get(spy)
            mdi = {d: i for i, d in enumerate(sp[0])}
            data_end = sp[0][-1]
        except Exception as e:
            S("ERR spy", str(e)[:150])
            return
        grp = {}
        for sid in self.sample:
            g = self._group(sid)
            if g:
                grp[sid] = g
        gc = {}
        for g in grp.values():
            gc[g] = gc.get(g, 0) + 1
        S("SM groups", f"sampled no-fund securities {len(self.sample)} | kept {len(grp)}: " + " ".join(f"{k} {v}" for k, v in sorted(gc.items())))
        syms = [self.sample[s] for s in grp]
        gof = {self.sample[s]: grp[s] for s in grp}
        C = {}

        def add(k, v=1):
            C[k] = C.get(k, 0) + v
        nsec = 0
        for a in range(0, len(syms), 60):
            chunk = syms[a:a + 60]
            try:
                fa = self._frame(chunk, DataNormalizationMode.ADJUSTED)
                fr = self._frame(chunk, DataNormalizationMode.RAW)
                fs = self._frame(chunk, DataNormalizationMode.SPLIT_ADJUSTED)
            except Exception as e:
                self.err.append(str(e)[:80])
                continue
            for s in chunk:
                if s not in fa:
                    continue
                ds, o, hi, c, v = fa[s]
                L = len(ds)
                if L < 3 or np.any(o <= 0) and np.sum(o <= 0) > L * 0.5:
                    continue
                nsec += 1
                G = gof.get(s, "?")
                md0 = np.array([mdi.get(dd, -1) for dd in ds])
                if np.any(np.diff(md0[md0 >= 0]) > 11):
                    add("sec_gap10")
                delisted = (data_end - ds[-1]).days > 7
                add("delisted", 1 if delisted else 0)
                md = np.array([mdi.get(d, -1) for d in ds])
                raw = fr.get(s)
                spl = fs.get(s)
                rc_t = raw[3] if raw is not None and len(raw[0]) == L else None
                for hz in HS:
                    if L <= hz + 1:
                        continue
                    n = L - hz - 1                     # complete windows t = 0..n-1
                    add(f"win{hz}", n)
                    e = o[1:n + 1]
                    okE = e > 0
                    mh = _swv(hi[1:], hz)[:n].max(axis=1)
                    mc = _swv(c[1:], hz)[:n].max(axis=1)
                    endc = c[hz:hz + n]
                    with np.errstate(divide="ignore", invalid="ignore"):
                        rA = np.where(okE, mh / e - 1, -1)
                        rB = np.where(okE, endc / e - 1, -1)
                        rBm = np.where(okE, mc / e - 1, -1)
                        rAc = np.where(c[:n] > 0, mh / c[:n] - 1, -1)
                    span = md[hz:hz + n] - md[1:n + 1]
                    missing = (span > hz - 1) | (md[1:n + 1] < 0)
                    vz = _swv(v[1:], hz)[:n].min(axis=1) <= 0
                    if raw is not None and len(raw[0]) == L:
                        ro, rh = raw[1][1:n + 1], _swv(raw[2][1:], hz)[:n].max(axis=1)
                        with np.errstate(divide="ignore", invalid="ignore"):
                            rR = np.where(ro > 0, rh / ro - 1, -1)
                    else:
                        rR = None
                    if spl is not None and len(spl[0]) == L:
                        so_, sh = spl[1][1:n + 1], _swv(spl[2][1:], hz)[:n].max(axis=1)
                        with np.errstate(divide="ignore", invalid="ignore"):
                            rS = np.where(so_ > 0, sh / so_ - 1, -1)
                    else:
                        rS = None
                    for th in TH:
                        key = f"{int(th * 100)}/{hz}"
                        evA = rA >= th
                        idx = np.nonzero(evA)[0]
                        add(f"A {key}", len(idx))
                        add(f"B {key}", int(np.sum(rB >= th)))
                        add(f"Bm {key}", int(np.sum(rBm >= th)))
                        add(f"Ac {key}", int(np.sum(rAc >= th)))
                        add(f"AnotB {key}", int(np.sum(evA & (rB < th))))
                        # episodes
                        ep, last = 0, -10 ** 9
                        for i in idx:
                            if i - last >= hz:
                                ep += 1
                                last = i
                        add(f"Aep {key}", ep)
                        add(f"Amiss {key}", int(np.sum(evA & missing)))
                        add(f"Avz {key}", int(np.sum(evA & vz)))
                        add(f"Agap10 {key}", int(np.sum(evA & (span > hz - 1 + 10))))
                        add(f"A {key} {G}", len(idx))
                        add(f"Aep {key} {G}", ep)
                        if rR is not None:
                            evR = rR >= th
                            add(f"R {key}", int(np.sum(evR)))
                            add(f"RnotA {key}", int(np.sum(evR & ~evA)))
                            add(f"AnotR {key}", int(np.sum(evA & ~evR)))
                        if rS is not None:
                            evS = rS >= th
                            add(f"S {key}", int(np.sum(evS)))
                            add(f"SxorA {key}", int(np.sum(evS ^ evA)))
                        if rc_t is not None and th == 1.0 and hz == 10:
                            px = rc_t[:n]
                            add("px<1", int(np.sum(evA & (px < 1))))
                            add("px1-5", int(np.sum(evA & (px >= 1) & (px < 5))))
                            add("px>=5", int(np.sum(evA & (px >= 5))))
                    # incomplete windows: t = n .. L-2 (at least one session after t)
                    for t in range(max(n, 0), L - 1):
                        add(f"inc{hz}")
                        et = o[t + 1]
                        if et <= 0:
                            continue
                        ma = hi[t + 1:].max() / et - 1
                        for th in TH:
                            key = f"{int(th * 100)}/{hz}"
                            if ma >= th:
                                add(f"incA {key}")
                            if delisted:
                                lastp = c[-1] / et - 1
                                if lastp >= th:
                                    add(f"incB_last {key}")
                                if 0.7 * c[-1] / et - 1 >= th:
                                    add(f"incB_70 {key}")
                    if delisted:
                        add(f"incdel{hz}", max(0, L - 1 - max(n, 0)))
        S("SM +100/10 by group (starts/episodes)", " ".join(f"{g} {C.get('A 100/10 ' + g, 0)}/{C.get('Aep 100/10 ' + g, 0)}" for g in ("ADDED-COMMON", "ADDED-ADR", "UNRESOLVED")) + f" | securities with a gap > 10 sessions {C.get('sec_gap10', 0)} | +100/10 events in windows crossing such a gap {C.get('Agap10 100/10', 0)}")
        S("SM sample", f"securities {nsec} of {len(syms)} sampled | delisted before data end {C.get('delisted', 0)} | windows 5/10/20d {C.get('win5', 0)} {C.get('win10', 0)} {C.get('win20', 0)}")
        for hz, th in ((5, 0.5), (10, 1.0), (20, 2.0), (10, 0.5), (20, 1.0)):
            k = f"{int(th * 100)}/{hz}"
            S(f"SM +{k} families", f"A {C.get('A ' + k, 0)} ep {C.get('Aep ' + k, 0)} | B {C.get('B ' + k, 0)} Bmax {C.get('Bm ' + k, 0)} A-not-B {C.get('AnotB ' + k, 0)} | A-closeref {C.get('Ac ' + k, 0)} | Amissing {C.get('Amiss ' + k, 0)} Azerovol {C.get('Avz ' + k, 0)}"[:198])
            S(f"SM +{k} adjustment", f"adj(TR) {C.get('A ' + k, 0)} raw {C.get('R ' + k, 0)} raw-not-adj {C.get('RnotA ' + k, 0)} adj-not-raw {C.get('AnotR ' + k, 0)} | split-only {C.get('S ' + k, 0)} differs-from-TR {C.get('SxorA ' + k, 0)}"[:198])
            S(f"SM +{k} incomplete", f"incomplete windows {C.get('inc' + str(hz), 0)} (delisted {C.get('incdel' + str(hz), 0)}) | A on available {C.get('incA ' + k, 0)} | B delisting: drop 0, last-price {C.get('incB_last ' + k, 0)}, last x0.7 {C.get('incB_70 ' + k, 0)}, zero 0"[:198])
        S("SM +100/10 A by raw price at t", f"<1 {C.get('px<1', 0)} 1-5 {C.get('px1-5', 0)} >=5 {C.get('px>=5', 0)}")
        if self.err:
            S("ERR", " | ".join(self.err)[:198])
