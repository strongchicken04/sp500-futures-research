# region imports
from AlgorithmImports import *
from datetime import date as _date
import numpy as np
import pandas as pd
from xup_s3_const import *
from xup_s4_core import *
from xup_s4_core import _o
# endregion
#
# Stage 4.5 core (research/extreme_upside/stage45/protocol.md): second-stage features and forward-path outcomes
# (wrapper around the Stage 4 _security wrapper; no Stage 3/4 array is changed), move-day events, ONSET_k labels,
# universe membership, frozen-RF state + transition features, timing-model training on rolling-origin folds,
# signals, event capture and placebo helpers. Aggregates only leave QC.

F45 = ["d_atr1", "d_atr3", "d_atr5", "rv3", "rv5_20", "range_rel20", "abs_r1", "dv_rel20", "vol_rel20", "dlogdv1", "dlogdv3",
       "dlogdv5", "wick_up", "wick_lo", "compress", "dsma20", "nbig10", "maxdd10", "dvmed20"]
FI45 = {k: i for i, k in enumerate(F45)}
P45 = ["A1", "A3", "A5", "A10", "B1", "B2", "B3", "B5", "B10", "M1", "M3", "M5", "M10", "L1", "L2", "L3", "L5", "L10", "dd5", "dd10", "tmin10", "tmax10b"]
PI45 = {k: i for i, k in enumerate(P45)}
FCU, FCD, FCH = (0.2, 0.3, 0.5), (0.05, 0.10, 0.15), (1, 3, 5)
FCL = [(u, d, h) for h in FCH for u in FCU for d in FCD]
FCI = {k: i for i, k in enumerate(FCL)}
UNIV = {"S0": (1.0, 1e5), "S1": (1.0, 5e5), "S2": (5.0, 1e6), "S5M": (5.0, 5e6), "A": (0.0, 0.0)}
G_STATE = ["rf"]
G_VACC = ["atr_p", "d_atr1", "d_atr3", "d_atr5", "rv3", "rv5_20", "range_rel20", "abs_r1"]
G_VOLU = ["dv_rel20", "vol_rel20", "dlogdv1", "dlogdv3", "dlogdv5", "vtrend"]
G_PATH = ["r1", "r3", "r5", "gap", "intraday", "clv", "wick_up", "wick_lo", "compress", "dsma20", "dhi20", "dlo20", "up_streak", "dn_streak", "nbig10", "maxdd10"]
G_TRANS = ["rf", "d_rf1", "d_rf3", "d_rf5", "run5", "enter5", "nent250", "since_ev", "nev250"]
GROUPS = {"VACC": G_VACC, "VOLU": G_VOLU, "PATH": G_PATH, "TRANS": G_TRANS}
FULL45 = list(dict.fromkeys(G_STATE + G_VACC + G_VOLU + G_PATH + G_TRANS))
TR0 = _o(2017, 1, 1)
FOLDS = {"a": (_o(2020, 12, 31) - 60, T0, _o(2022, 12, 31)), "b": (_o(2022, 12, 31) - 60, _o(2023, 1, 1), T1), "c": (_o(2025, 12, 31) - 60, Y0, Y1)}
HP_TR1, HP_V0, HP_V1 = _o(2019, 12, 31) - 60, _o(2020, 1, 1), _o(2020, 12, 31)
C_GRID, LEAF_GRID = (0.01, 0.1, 1.0), (20, 50, 100)
# cost scenarios (protocol 8): set by amendment after S45EXEC, before S45OUTCOME; None = not yet measured
S30 = None


class S45Core:

    # ---------------- panel extension: wraps the Stage 4 wrapper ----------------
    def _security(self, sid, cls, adj, raw):
        r = self._security_s4(sid, cls, adj, raw)
        if r is None:
            return None
        if not hasattr(self, "X45"):
            self.X45 = []
        n = len(r[0])
        try:
            ex = self._s45_extras(adj, raw, r[0])
        except Exception as e:
            self.err.append("s45x " + type(e).__name__)
            ex = (np.full((n, len(F45)), np.nan, np.float32), np.full((n, len(P45)), np.nan, np.float32), np.full((n, len(FCL)), -1, np.int8))
        self.X45.append(ex)
        return r

    def _s45_align(self, adj, raw):
        ds, o, hi, lo, c, v = adj
        rds, ro, rh, rl, rc, rv = raw
        if len(ds) != len(rds) or not np.array_equal(ds, rds):
            m = {d: i for i, d in enumerate(rds)}
            idx = np.array([m.get(d, -1) for d in ds])
            ok = idx >= 0
            ds, o, hi, lo, c, v = ds[ok], o[ok], hi[ok], lo[ok], c[ok], v[ok]
            rc, rv = rc[idx[ok]], rv[idx[ok]]
        md = np.array([self.mdi.get(int(d), -1) for d in ds])
        k = md >= 0
        return ds[k], o[k], hi[k], lo[k], c[k], v[k], rc[k], rv[k], md[k]

    def _s45_feats_seg(self, oo, hh, ll, cc, RC, RV):
        """features of one segment (trailing windows only); returns (n, len(F45)) float64"""
        n = len(cc)
        out = np.full((n, len(F45)), np.nan)
        C, H, L, O = pd.Series(cc), pd.Series(hh), pd.Series(ll), pd.Series(oo)
        lr = np.log(C.where(C > 0)).diff()
        tr = pd.concat([H - L, (H - C.shift(1)).abs(), (L - C.shift(1)).abs()], axis=1).max(axis=1)
        atr = tr.rolling(14, min_periods=14).mean() / C
        for k in (1, 3, 5):
            out[:, FI45[f"d_atr{k}"]] = (atr / atr.shift(k) - 1).values
        rv5 = lr.rolling(5, min_periods=5).std(); rv20 = lr.rolling(20, min_periods=20).std()
        out[:, FI45["rv3"]] = lr.rolling(3, min_periods=3).std().values
        out[:, FI45["rv5_20"]] = (rv5 / rv20.where(rv20 > 0)).values
        rng = (H - L) / C
        med20 = rng.shift(1).rolling(20, min_periods=20).median()
        out[:, FI45["range_rel20"]] = (rng / med20.where(med20 > 0)).values
        out[:, FI45["abs_r1"]] = lr.abs().values
        DV = pd.Series(RC * RV); V = pd.Series(RV)
        mdv = DV.shift(1).rolling(20, min_periods=20).median(); mv = V.shift(1).rolling(20, min_periods=20).median()
        out[:, FI45["dv_rel20"]] = (DV / mdv.where(mdv > 0)).values
        out[:, FI45["vol_rel20"]] = (V / mv.where(mv > 0)).values
        ldv = np.log1p(DV)
        for k in (1, 3, 5):
            out[:, FI45[f"dlogdv{k}"]] = (ldv - ldv.shift(k)).values
        hl = (H - L)
        out[:, FI45["wick_up"]] = np.where(hl > 0, (H - np.maximum(O, C)) / hl.where(hl > 0), 0.0)
        out[:, FI45["wick_lo"]] = np.where(hl > 0, (np.minimum(O, C) - L) / hl.where(hl > 0), 0.0)
        m5 = rng.rolling(5, min_periods=5).median(); m20 = rng.rolling(20, min_periods=20).median()
        out[:, FI45["compress"]] = (m5 / m20.where(m20 > 0)).values
        out[:, FI45["dsma20"]] = (C / C.rolling(20, min_periods=20).mean() - 1).values
        med60 = rng.shift(1).rolling(60, min_periods=60).median()
        big = (rng > 2 * med60).astype(float).where(med60.notna())
        out[:, FI45["nbig10"]] = big.rolling(10, min_periods=10).sum().values
        dd = C / C.rolling(10, min_periods=1).max() - 1
        out[:, FI45["maxdd10"]] = dd.rolling(10, min_periods=10).min().values
        out[:, FI45["dvmed20"]] = DV.rolling(20, min_periods=20).median().values
        return out

    def _s45_extras(self, adj, raw, keep_dates, return_all=False):
        ds, o, hi, lo, c, v, rc, rv, md = self._s45_align(adj, raw)
        n = len(ds)
        seg = np.concatenate([[0], np.cumsum(np.diff(md) > 11)])
        FE = np.full((n, len(F45)), np.nan)
        PO = np.full((n, len(P45)), np.nan, dtype=np.float32)
        FC = np.full((n, len(FCL)), -1, dtype=np.int8)
        endm = self.mdi[DATA_END.toordinal()] if DATA_END.toordinal() in self.mdi else 10 ** 9
        sw = np.lib.stride_tricks.sliding_window_view
        for sg in np.unique(seg):
            ii = np.nonzero(seg == sg)[0]
            a, b = ii[0], ii[-1] + 1
            ns = b - a
            oo, hh, ll, cc, MD = o[a:b], hi[a:b], lo[a:b], c[a:b], md[a:b]
            FE[a:b] = self._s45_feats_seg(oo, hh, ll, cc, rc[a:b], rv[a:b])
            for h in (1, 2, 3, 5, 10):
                m = ns - h
                if m <= 0:
                    continue
                ref = oo[1:m + 1]
                okr = (ref > 0) & (MD[h:h + m] <= endm)
                Wh, Wl, Wc = sw(hh[1:], h)[:m], sw(ll[1:], h)[:m], sw(cc[1:], h)[:m]
                rr = ref[:, None]
                with np.errstate(divide="ignore", invalid="ignore"):
                    put = lambda nm, val: PO.__setitem__((slice(a, a + m), PI45[nm]), np.where(okr, val, np.nan))
                    if h in (1, 3, 5, 10):
                        put(f"A{h}", Wh.max(axis=1) / ref - 1)
                        put(f"M{h}", Wc.max(axis=1) / ref - 1)
                    put(f"B{h}", cc[h:h + m] / ref - 1)
                    put(f"L{h}", Wl.min(axis=1) / ref - 1)
                    if h in (5, 10):
                        pm = np.maximum.accumulate(Wh, axis=1)
                        P = np.concatenate([rr, np.maximum(rr, pm[:, :-1])], axis=1)
                        put(f"dd{h}", (Wl / P).min(axis=1) - 1)
                    if h == 10:
                        put("tmin10", Wl.argmin(axis=1) + 1)
                        put("tmax10b", Wh.argmax(axis=1) + 1)
                    if h in FCH:
                        for u in FCU:
                            uh = Wh >= (1 + u) * rr
                            fu = np.where(uh.any(axis=1), uh.argmax(axis=1), h + 1)
                            for d in FCD:
                                dh = Wl <= (1 - d) * rr
                                fd = np.where(dh.any(axis=1), dh.argmax(axis=1), h + 1)
                                code = np.where((fu > h) & (fd > h), 0, np.where(fu < fd, 1, np.where(fd < fu, 2, 3)))
                                FC[a:a + m, FCI[(u, d, h)]] = np.where(okr, code, -1).astype(np.int8)
        if return_all:
            return ds, FE
        idx = np.searchsorted(ds, keep_dates)
        if np.any(idx >= n) or not np.array_equal(ds[np.minimum(idx, n - 1)], keep_dates):
            raise ValueError("s45 date alignment")
        return FE[idx].astype(np.float32), PO[idx], FC[idx]

    def _s45_finish(self):
        if getattr(self, "s45_ready", False):
            return
        self._s4_finish()
        X = self.X45
        assert len(X) == len(self.sid_list), "X45 / parts misaligned"
        self.FE = np.concatenate([x[0] for x in X])
        self.PO = np.concatenate([x[1] for x in X])
        self.FCA = np.concatenate([x[2] for x in X])
        self.X45 = None
        assert len(self.PO) == len(self.D)
        mis = []
        for a, b in (("A10", "mh10"), ("B5", "c5"), ("B10", "c10"), ("M10", "mc10"), ("L10", "ml10")):
            x, y = self.PO[:, PI45[a]], self.OUT[:, OI[b]]
            nm = int((np.isnan(x) != np.isnan(y)).sum())
            f = np.isfinite(x) & np.isfinite(y)
            vm = int((np.abs(x[f] - y[f]) > 1e-6 * np.maximum(1, np.abs(y[f]))).sum())
            mis.append(f"{a}:{nm}/{vm}")
        errs = sum(1 for e in self.err if e.startswith("s45x"))
        self.s45_ok = all(m.endswith(":0/0") for m in mis) and errs == 0 and self.s4_ok
        self.set_runtime_statistic("S45 CHECK", ("OK " if self.s45_ok else "FAILED ") + f"path outcomes vs Stage 4 (nan/value mismatches) {' '.join(mis)} | s45 extension errors {errs} | S4 {'OK' if self.s4_ok else 'FAILED'}")
        # derived arrays
        self.RC = self.PX
        self.DVMED = self.FE[:, FI45["dvmed20"]].astype(np.float64)
        self.s45_ready = True

    # ---------------- universes ----------------
    def _s45_umask(self, name, rule="trail"):
        p, d = UNIV[name]
        if name == "A":
            return self.U["A"].copy()
        dv = self.DVMED if rule == "trail" else self.DV
        return self.U["A"] & (self.RC >= p) & (np.nan_to_num(dv, nan=-1) >= d)

    # ---------------- move-day events ----------------
    def _s45_moves(self, defn):
        """events with move day tau1 and last move activity tauL (global row indices), sorted by tau1"""
        if defn == "E3":
            ev = self._s4_events(PRIMARY, "E3")
            t1, tl = ev["start"].copy(), ev["last"].copy()
        else:
            fam, rule, tcol = {"E1": ("A", "E1", "t100"), "E2": ("A", "E2", "t100"), "B": ("B", "E1", "tc100"), "M": ("M", "E1", "tc100")}[defn]
            li = TI[(fam, 10, 1.0)]
            ev = self._s4_events(li, rule)
            pos = np.nonzero(self.L[:, li] == 1)[0]
            eid = np.searchsorted(ev["start"], pos, side="right") - 1
            ok = (eid >= 0) & (pos <= ev["last"][np.maximum(eid, 0)])
            pos, eid = pos[ok], eid[ok]
            off = self.OUT[pos, OI[tcol]]
            good = np.isfinite(off) & (off > 0)
            cross = (pos + np.where(good, off, 0)).astype(np.int64)
            t1 = np.full(len(ev["start"]), -1, dtype=np.int64); tl = np.full(len(ev["start"]), -1, dtype=np.int64)
            df = pd.DataFrame({"e": eid[good], "x": cross[good]}).groupby("e")["x"].agg(["min", "max"])
            t1[df.index.values] = df["min"].values; tl[df.index.values] = df["max"].values
            k = t1 >= 0
            t1, tl = t1[k], tl[k]
        o = np.argsort(t1, kind="mergesort")
        t1, tl = t1[o], tl[o]
        return dict(t1=t1, tl=tl, sid=self.SID[t1], date=self.D[t1])

    def _s45_onset(self, mv, k, excl_back=10):
        """ONSET_k labels: 1 / 0 / -1 invalid (window incomplete) / -2 excluded (move day in [t-10, t])"""
        n = len(self.D)
        flag = np.zeros(n, dtype=np.int32)
        np.add.at(flag, mv["t1"], 1)
        cm = np.concatenate([[0], np.cumsum(flag)])
        t = np.arange(n)
        lo = np.maximum(t - excl_back, self.SEG0)
        recent = (cm[t + 1] - cm[lo]) > 0
        hi = np.minimum(t + k, self.SEG1)
        fut = (cm[hi + 1] - cm[t + 1]) > 0
        lab = np.where(fut, 1, np.where(t + k > self.SEG1, -1, 0)).astype(np.int8)
        lab[recent] = -2
        return lab

    def _s45_movecount(self, mv):
        n = len(self.D)
        flag = np.zeros(n, dtype=np.int32)
        np.add.at(flag, mv["t1"], 1)
        return np.concatenate([[0], np.cumsum(flag)]), flag

    # ---------------- state and transition features ----------------
    def _s45_scores(self):
        if not hasattr(self, "sc45"):
            scM = self._s4_score(["fullA RF"], False, VSCORE, V1)["fullA RF"]
            scT = self._s4_score(["fullA RF"], True, SCORE_START, Y1)["fullA RF"]
            self.sc45 = (scM, scT)
        return self.sc45

    def _s45_state(self, uname, rule="trail"):
        """RF percentile inside the universe (MODEL-split before 2021, TEST-split from 2021) and transition features"""
        key = (uname, rule)
        if not hasattr(self, "st45"):
            self.st45 = {}
        if key in self.st45:
            return self.st45[key]
        scM, scT = self._s45_scores()
        um = self._s45_umask(uname, rule)
        n = len(self.D)
        out = {}
        parts = []
        for sc, lo, hi in ((scM, VSCORE, V1), (scT, SCORE_START, Y1)):
            m = um & np.isfinite(sc) & (self.D >= lo) & (self.D <= hi)
            rows = np.nonzero(m)[0]
            pr = np.full(n, np.nan)
            pr[rows] = self._dayrank(sc[rows], self.D[rows])
            parts.append(self._s45_trans(pr))
        use_t = self.D >= T0
        for k in parts[0]:
            out[k] = np.where(use_t, parts[1][k], parts[0][k])
        out["umask"] = um
        self.st45[key] = out
        return out

    def _s45_trans(self, pr):
        """transition features from a percentile series (NaN where not scored / not in universe), within segments"""
        n = len(self.D)
        rf = 1 - pr
        g = self.GS
        same = lambda k: np.concatenate([np.zeros(k, dtype=bool), g[k:] == g[:-k]])
        out = {"pr": pr, "rf": rf}
        for k in (1, 3, 5):
            sh = np.full(n, np.nan); sh[k:] = rf[:-k]
            out[f"d_rf{k}"] = np.where(same(k), rf - sh, np.nan)
        in5 = np.nan_to_num(pr, nan=9) <= 0.05
        prev5 = np.zeros(n, dtype=bool); prev5[1:] = in5[:-1] & same(1)[1:]
        enter = in5 & ~prev5
        # run length of consecutive P5 rows within segment
        brk = ~in5 | ~np.concatenate([[False], same(1)[1:]])
        grp = np.cumsum(brk)
        run = pd.Series(in5.astype(int)).groupby(grp).cumsum().values
        out["run5"] = np.where(in5, run, 0).astype(float)
        out["enter5"] = enter.astype(float)
        ce = np.concatenate([[0], np.cumsum(enter)])
        t = np.arange(n)
        lo = np.maximum(t - 249, self.SEG0)
        out["nent250"] = (ce[t + 1] - ce[lo]).astype(float)
        return out

    def _s45_evhist(self, mv):
        n = len(self.D)
        cm, flag = self._s45_movecount(mv)
        t = np.arange(n)
        lo = np.maximum(t - 249, self.SEG0)
        nev = (cm[t + 1] - cm[lo]).astype(float)
        last = np.where(flag > 0, t, -1)
        last = pd.Series(last).groupby(self.GS).cummax().values
        since = np.where((last >= 0) & (last >= self.SEG0), t - last, 500).clip(max=500).astype(float)
        return {"nev250": nev, "since_ev": since}

    # ---------------- feature matrix ----------------
    def _s45_X(self, rows, feats, st, eh):
        cols = []
        for f in feats:
            if f in FI45:
                cols.append(self.FE[rows, FI45[f]].astype(np.float64))
            elif f in st:
                cols.append(st[f][rows])
            elif f in eh:
                cols.append(eh[f][rows])
            else:
                cols.append(self.F[rows, FI[f]].astype(np.float64))
        return np.column_stack(cols)

    # ---------------- population, training, scoring ----------------
    def _s45_pop(self, uname="S1", kst=0.05, defn="E1", k=3, rule="trail"):
        """ex-ante population mask (universe & state & not recently moved) and label array"""
        key = ("pop", uname, kst, defn, k, rule)
        if not hasattr(self, "pc45"):
            self.pc45 = {}
        if key in self.pc45:
            return self.pc45[key]
        st = self._s45_state(uname, rule)
        mv = self._s45_mv(defn)
        lab = self._s45_onset(mv, k)
        exante = st["umask"] & (np.nan_to_num(st["pr"], nan=9) <= kst) & (lab != -2)
        res = (exante, lab, st)
        self.pc45[key] = res
        return res

    def _s45_mv(self, defn):
        if not hasattr(self, "mv45"):
            self.mv45 = {}
        if defn not in self.mv45:
            self.mv45[defn] = self._s45_moves(defn)
        return self.mv45[defn]

    def _s45_fit(self, kind, X, y, hp):
        from sklearn.linear_model import LogisticRegression
        from sklearn.ensemble import RandomForestClassifier
        Z, prep = self._prep(X)
        if kind == "rf":
            m = RandomForestClassifier(n_estimators=300, min_samples_leaf=hp, max_features="sqrt", n_jobs=1, random_state=7).fit(Z, y)
        else:
            m = LogisticRegression(C=hp, max_iter=1000).fit(Z, y)
        return lambda A: m.predict_proba(self._prep(A, prep)[0])[:, 1]

    def _s45_hp(self, exante, lab, st, eh):
        """choose L2 C and RF leaf on train 2017..2019-60d / validate 2020 (S1-P5 ONSET_3); frozen afterwards"""
        if hasattr(self, "hp45"):
            return self.hp45
        tr = exante & (lab >= 0) & (self.D >= TR0) & (self.D <= HP_TR1)
        va = exante & (lab >= 0) & (self.D >= HP_V0) & (self.D <= HP_V1)
        rt, rv = np.nonzero(tr)[0], np.nonzero(va)[0]
        Xt, yt = self._s45_X(rt, FULL45, st, eh), (lab[rt] == 1).astype(int)
        Xv, yv = self._s45_X(rv, FULL45, st, eh), (lab[rv] == 1).astype(float)
        res = {}
        for kind, grid in (("l2", C_GRID), ("rf", LEAF_GRID)):
            sc = []
            for hp in grid:
                f = self._s45_fit(kind, Xt, yt, hp)
                s = f(Xv)
                o = np.argsort(-s, kind="mergesort")
                sc.append((self._ap_sorted(yv[o], np.ones(len(yv))), hp))
            res[kind] = max(sc)[1]
            res[kind + "_grid"] = " ".join(f"{hp}:{ap:.4f}" for ap, hp in sc)
        res["n"] = f"train rows {len(rt)} pos {int(yt.sum())} | valid rows {len(rv)} pos {int(yv.sum())}"
        self.hp45 = res
        return res

    def _s45_models(self, exante, lab, st, eh, specs, folds=("a", "b")):
        """fit each spec on each fold's training window, score that fold's test rows; returns {name: score array}"""
        n = len(self.D)
        out = {nm: np.full(n, np.nan) for nm, _, _ in specs}
        for fo in folds:
            trend, te0, te1 = FOLDS[fo]
            tr = exante & (lab >= 0) & (self.D >= TR0) & (self.D <= trend)
            te = exante & (self.D >= te0) & (self.D <= te1)
            rt, rte = np.nonzero(tr)[0], np.nonzero(te)[0]
            yt = (lab[rt] == 1).astype(int)
            for nm, kind, feats in specs:
                if kind == "state":
                    out[nm][rte] = st["rf"][rte]
                    continue
                hp = 1e4 if kind == "lr" else (self.hp45["l2"] if kind == "l2" else self.hp45["rf"])
                f = self._s45_fit("rf" if kind == "rf" else "lr", self._s45_X(rt, feats, st, eh), yt, hp)
                out[nm][rte] = f(self._s45_X(rte, feats, st, eh))
        return out

    def _s45_signals(self, score, exante, q=0.10):
        rows = np.nonzero(exante & np.isfinite(score))[0]
        pr = self._dayrank(score[rows], self.D[rows])
        sig = np.zeros(len(self.D), dtype=bool)
        sig[rows[pr <= q]] = True
        return sig

    def _s45_capture(self, mv, sel, sig, popex, k=3):
        """per selected event: eligible (>=1 population row in tau-k..tau-1), captured (>=1 signal there), first lead"""
        t1 = mv["t1"][sel]
        s0 = self.SEG0[t1]
        lo = np.maximum(t1 - k, s0)
        cp = np.concatenate([[0], np.cumsum(popex)]); cs = np.concatenate([[0], np.cumsum(sig)])
        elig = (t1 > lo) & ((cp[t1] - cp[lo]) > 0)
        cap = (t1 > lo) & ((cs[t1] - cs[lo]) > 0)
        lead = np.zeros(len(t1), dtype=int)
        for j in np.nonzero(cap)[0]:
            w = np.nonzero(sig[lo[j]:t1[j]])[0]
            lead[j] = t1[j] - (lo[j] + w[0])
        return elig, cap, lead, mv["sid"][sel]

    def _s45_window(self, mv, sel, sig, a, b, member=None, sig_start=None):
        """detection of >=1 signal in rows tau-b..tau-a (same segment, inside the signal period); returns ok, det"""
        t1 = mv["t1"][sel]
        lo, hi = t1 - b, t1 - a
        ok = (lo >= self.SEG0[t1]) & (self.D[np.maximum(lo, 0)] >= (T0 if sig_start is None else sig_start))
        cs = np.concatenate([[0], np.cumsum(sig)])
        lo2, hi2 = np.maximum(lo, 0), np.maximum(hi, 0)
        det = ok & ((cs[hi2 + 1] - cs[lo2]) > 0)
        if member is not None:
            cm = np.concatenate([[0], np.cumsum(~member)])
            ok &= (cm[hi2 + 1] - cm[lo2]) == 0
        return ok, det
