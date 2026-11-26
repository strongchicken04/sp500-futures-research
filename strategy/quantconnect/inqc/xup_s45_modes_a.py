# region imports
from AlgorithmImports import *
from datetime import date as _date
import hashlib
import numpy as np
import pandas as pd
from xup_s3_const import *
from xup_s4_core import *
from xup_s4_core import _o
from xup_s45_core import *
# endregion
#
# Stage 4.5: S45AUDIT (events, onset labels, populations, denominators) and S45FEATURE (leakage tests, coverage,
# exploratory univariate feature tests on the training window only).

PERIODS = [("train17-20", TR0, FOLDS["a"][0]), ("val2020", HP_V0, HP_V1), ("t21-22", T0, _o(2022, 12, 31)), ("t23-25", _o(2023, 1, 1), T1), ("y2026", Y0, Y1)]


class S45ModesA:

    def mode_s45audit(self):
        S = self.set_runtime_statistic
        self._s45_finish()
        base = self.U["A"] & (self.D >= VSCORE)
        for defn in ("E1", "E2", "E3", "B", "M"):
            mv = self._s45_mv(defn)
            d = mv["date"]
            nt = int(((d >= T0) & (d <= T1)).sum()); ny = int((d >= Y0).sum()); ntr = int(((d >= TR0) & (d <= V1)).sum())
            parts = []
            for k in (1, 2, 3, 5):
                lab = self._s45_onset(mv, k)
                lb = lab[base]
                parts.append(f"k{k} +{int((lb == 1).sum())}/0 {int((lb == 0).sum())}/inv {int((lb == -1).sum())}/excl {int((lb == -2).sum())}")
            dup = len(mv["t1"]) - len(np.unique(mv["t1"]))
            S(f"L1 {defn} moves", (f"events {len(mv['t1'])} (same-day duplicates {dup}) | 2017-20 {ntr} 2021-25 {nt} 2026 {ny} | rows>=2016-11: " + " ".join(parts))[:198])
        mv = self._s45_mv("E1")
        ev = self._s4_events(PRIMARY, "E1")
        st0 = np.sort(ev["start"])
        j = np.searchsorted(st0, mv["t1"], side="right") - 1
        lead = mv["t1"] - st0[np.maximum(j, 0)]
        S("L2 E1 label onset vs move day", f"sessions from first positive label row to move day p10/50/90 {q(lead, (10, 50, 90))} | move days {len(mv['t1'])} vs E1 episodes {len(ev['start'])}")
        # populations x periods
        pops = [("S1", 0.05, "trail"), ("S1", 0.01, "trail"), ("S1", 0.10, "trail"), ("S2", 0.05, "trail"), ("S0", 0.05, "trail"), ("S5M", 0.05, "trail"), ("A", 0.05, "trail"), ("S1", 0.05, "day")]
        for un, kst, rule in pops:
            exante, lab, st = self._s45_pop(un, kst, "E1", 3, rule)
            um = st["umask"]
            parts = []
            for tag, lo, hi in PERIODS:
                per = (self.D >= lo) & (self.D <= hi)
                pv = exante & per & (lab >= 0)
                npos = int((lab[pv] == 1).sum())
                sel = (mv["date"] >= lo) & (mv["date"] <= hi)
                elig, cap, ld, sd = self._s45_capture(mv, sel, np.zeros(len(self.D), dtype=bool), exante & per, 3)
                inu = um[np.maximum(mv["t1"][sel] - 1, 0)]
                nd = len(np.unique(self.D[exante & per]))
                excl = int((um & per & (np.nan_to_num(st["pr"], nan=9) <= kst) & (lab == -2)).sum())
                parts.append(f"{tag}: rows {int(pv.sum())} secs {len(np.unique(self.SID[pv]))} pos {npos} base {100 * npos / max(pv.sum(), 1):.2f}% ev {int(elig.sum())}/{int(inu.sum())} rows/day {pv.sum() / max(nd, 1):.1f} excl {excl}")
            line = f"{un}-P{int(kst * 100)} {rule}: " + " | ".join(parts)
            if un == "S1" and kst == 0.05 and rule == "trail":
                S("L3 S1-P5 primary a", line[:198]); S("L3 S1-P5 primary b", (" | ".join(parts[2:]))[:198])
            self.lg("POP " + line)
        # universe sizes per day (test)
        per = (self.D >= T0) & (self.D <= T1)
        parts = []
        for un in ("S0", "S1", "S2", "S5M", "A"):
            for rule in ("trail", "day"):
                um = self._s45_umask(un, rule) & per
                c = pd.Series(1, index=self.D[um]).groupby(level=0).sum()
                parts.append(f"{un}/{rule} {np.median(c.values) if len(c) else 0:.0f}")
        S("L4 universe rows/day (test, median)", " ".join(parts)[:198])
        self.lg("CHECK " + self.s4_check)

    # ---------------- feature leakage tests ----------------
    def mode_s45feature(self):
        S = self.set_runtime_statistic
        self._s45_finish()
        nb = np.bincount(self.SID)
        cand = [i for i in range(len(self.sid_list)) if nb[i] >= 500]
        cand = sorted(cand, key=lambda i: hashlib.md5(f"lk|{self.sid_list[i]}".encode()).hexdigest())[:25]
        mism = np.zeros(len(F45), dtype=int)
        ntest, nfail_sec = 0, 0
        rng = np.random.RandomState(45)
        for i in cand:
            sym = self.syms.get(self.sid_list[i])
            if sym is None:
                continue
            try:
                fa = self._hist([sym], DataNormalizationMode.ADJUSTED).get(sym)
                fr = self._hist([sym], DataNormalizationMode.RAW).get(sym)
            except Exception:
                nfail_sec += 1
                continue
            if fa is None or fr is None:
                nfail_sec += 1
                continue
            ds, FEf = self._s45_extras(fa, fr, None, return_all=True)
            rows = np.nonzero(self.SID == i)[0]
            dts = self.D[rows]
            picks = sorted(dts, key=lambda d: hashlib.md5(f"{i}|{d}".encode()).hexdigest())[:3]
            for d in picks:
                ka = np.searchsorted(fa[0], d, side="right"); kr = np.searchsorted(fr[0], d, side="right")
                tra = tuple(x[:ka] for x in fa); trr = tuple(x[:kr] for x in fr)
                mod_a = tuple(np.concatenate([x[:ka], x[ka:] * (rng.uniform(0.3, 3.0, len(x) - ka) if j > 0 else 1)]) if j > 0 else x for j, x in enumerate(fa))
                mod_r = tuple(np.concatenate([x[:kr], x[kr:] * (rng.uniform(0.3, 3.0, len(x) - kr) if j > 0 else 1)]) if j > 0 else x for j, x in enumerate(fr))
                d1, F1 = self._s45_extras(tra, trr, None, return_all=True)
                d2, F2 = self._s45_extras(mod_a, mod_r, None, return_all=True)
                p0, p1, p2 = np.searchsorted(ds, d), np.searchsorted(d1, d), np.searchsorted(d2, d)
                if p0 >= len(ds) or ds[p0] != d or p1 >= len(d1) or d1[p1] != d or d2[p2] != d:
                    continue
                for a in (F1[p1], F2[p2]):
                    b = FEf[p0]
                    bad = (np.isnan(a) != np.isnan(b)) | (np.isfinite(a) & np.isfinite(b) & (np.abs(a - b) > 1e-9 * np.maximum(1, np.abs(b))))
                    mism += bad
                ntest += 1
        S("F1 leakage test (per-security recompute)", f"securities {len(cand)} (fetch failures {nfail_sec}) x 3 dates = {ntest} (security, t) tests x 2 (truncated, future replaced) | mismatches total {int(mism.sum())}"
          + (" | failing: " + ",".join(F45[j] for j in np.nonzero(mism)[0]) if mism.any() else ""))
        # state-transition and event-history features: randomise everything after a cut date
        st = self._s45_state("S1")
        mv = self._s45_mv("E1")
        eh = self._s45_evhist(mv)
        bad_t = 0; nchk = 0
        ref = self._s45_trans(st["pr"])
        for cut in (_o(2022, 6, 30), _o(2024, 3, 29)):
            pr = st["pr"].copy()
            after = self.D > cut
            pr[after] = rng.uniform(0, 1, int(after.sum()))
            tr2 = self._s45_trans(pr)
            keep = (self.D <= cut) & (self.D >= T0) & np.isfinite(st["pr"])
            for kf in ("rf", "d_rf1", "d_rf3", "d_rf5", "run5", "enter5", "nent250"):
                a, b = ref[kf][keep], tr2[kf][keep]
                ok = (np.isnan(a) == np.isnan(b)) & ((np.isnan(a)) | (np.abs(a - b) < 1e-12))
                bad_t += int((~ok).sum())
            mv2 = dict(t1=mv["t1"][mv["date"] <= cut])
            eh2 = self._s45_evhist(mv2)
            for kf in ("nev250", "since_ev"):
                a, b = eh[kf][keep], eh2[kf][keep]
                bad_t += int((a != b).sum())
            nchk += int(keep.sum())
        S("F2 leakage test (state / event-history)", f"rows checked {nchk} over 2 cut dates (all later percentiles randomised, later move days removed) | mismatches {bad_t}")
        # coverage and exploratory univariate AUC on the TRAINING window only
        exante, lab, st = self._s45_pop("S1", 0.05, "E1", 3)
        tr = exante & (lab >= 0) & (self.D >= TR0) & (self.D <= FOLDS["a"][0])
        te = exante & (lab >= 0) & (self.D >= T0) & (self.D <= T1)
        rt = np.nonzero(tr)[0]
        y = (lab[rt] == 1).astype(float)
        sid = self.SID[rt]
        nsec = int(self.SID.max()) + 1
        W = self._boot_W(300, 4504, nsec)
        res = []
        cov = []
        for f in FULL45:
            x = self._s45_X(rt, [f], st, eh)[:, 0]
            xt = self._s45_X(np.nonzero(te)[0], [f], st, eh)[:, 0]
            cov.append(f"{f} {100 * np.isfinite(x).mean():.0f}/{100 * np.isfinite(xt).mean():.0f}")
            fin = np.isfinite(x)
            if fin.sum() < 100 or y[fin].sum() < 5:
                continue
            xs, ys, ss = x[fin], y[fin], sid[fin]
            o = np.argsort(xs, kind="mergesort"); ysrt = ys[o]; ssrt = ss[o]
            def wauc(w):
                wp = w * ysrt; wn = w * (1 - ysrt)
                return float((wp * (np.cumsum(wn) - wn)).sum() / max(wp.sum() * wn.sum(), 1e-9))
            a0 = wauc(np.ones(len(ysrt)))
            ba = np.array([wauc(W[b][ssrt]) for b in range(300)])
            p = min(1.0, max(2 * min((ba <= 0.5).mean(), (ba >= 0.5).mean()), 1 / 300))
            res.append((f, a0, np.percentile(ba, 2.5), np.percentile(ba, 97.5), p))
        ps = np.array([r[4] for r in res]); o = np.argsort(ps); qv = np.empty(len(ps)); mn = 1.0
        for r in range(len(ps) - 1, -1, -1):
            mn = min(mn, ps[o[r]] * len(ps) / (r + 1)); qv[o[r]] = mn
        sig = [f"{r[0]} {r[1]:.3f}" for r, qq in zip(res, qv) if qq < 0.05]
        S("F3 univariate (training 2017-20 only, exploratory)", f"S1-P5 ONSET_3 training rows {len(rt)} pos {int(y.sum())} | features tested {len(res)}, BH q<0.05: {len(sig)}")
        self.lg("F3 AUC [95% CI] p q (feature vs ONSET_3, S1-P5, training window; AUC<0.5 = lower values before onsets): " + " | ".join(f"{r[0]} {r[1]:.3f} [{r[2]:.3f},{r[3]:.3f}] q{qq:.3f}" for r, qq in zip(res, qv)))
        self.lg("F4 coverage % finite (training / test rows of S1-P5): " + " ".join(cov))
        self.lg("CHECK " + self.s4_check)
