# region imports
from AlgorithmImports import *
import numpy as np
import pandas as pd
from xup_s3_const import *
from xup_s4_core import *
from xup_s4_core import _o
from xup_s45_core import *
# endregion
#
# Stage 4.5: S45OUTCOME (protocol 7-9): capturable targets (Families A, B, B-max, C), C4 short list, downside (C5),
# success / failure split, payoff proxy with cost scenarios (C7), Family A vs B/C capture, S2 direction (C6).
# Groups (test 2021-25): G0 unconditional S1, G1 S1-P5 conditional population, G2 STATE signals, G3 L2 timing signals.

P21 = (T0, _o(2022, 12, 31)); P23 = (_o(2023, 1, 1), T1)
SHORT = ["CB3_20", "CB5_50", "FC3_20_10", "FC5_30_10", "FC5_50_15"]


class S45ModesD:

    def _s45_tgt(self, name):
        """hit indicator over all rows (1/0, NaN = incomplete) for a target name"""
        if name.startswith("FC"):
            h, u, d = name[2:].split("_")
            code = self.FCA[:, FCI[(int(u) / 100, int(d) / 100, int(h))]]
            return np.where(code < 0, np.nan, (code == 1).astype(float))
        fam, rest = (name[:2], name[2:]) if name.startswith("CB") else (name[:1], name[1:])
        h, thr = rest.split("_")
        col = {"A": "A", "B": "B", "CB": "M"}[fam] + h
        x = self.PO[:, PI45[col]].astype(np.float64)
        return np.where(np.isfinite(x), (x >= int(thr) / 100 - 1e-12).astype(float), np.nan)

    def _s45_fam(self):
        A = [f"A{h}_{t}" for h in (1, 3, 5, 10) for t in (50, 100, 200)]
        B = [f"B{h}_{t}" for h in (1, 3, 5, 10) for t in (20, 50, 100)]
        M = [f"CB{h}_{t}" for h in (1, 3, 5, 10) for t in (20, 50, 100)]
        C = [f"FC{h}_{int(u * 100)}_{int(d * 100)}" for h in FCH for u in FCU for d in FCD]
        return {"A": A, "B": B, "B-max": M, "C": C}

    def _s45_gb(self, x, rows_a, rows_b, W, nsec):
        """security-bootstrap of mean(x[rows_a]) - mean(x[rows_b]) (rows_b None: one-sample mean); NaN rows dropped"""
        def sums(rows):
            v = x[rows]; f = np.isfinite(v)
            s = self.SID[rows][f]
            return np.bincount(s, weights=v[f], minlength=nsec), np.bincount(s, minlength=nsec).astype(float), v[f].mean() if f.any() else np.nan
        na, da, ma = sums(rows_a)
        ba = (W @ na) / np.maximum(W @ da, 1e-9)
        if rows_b is None:
            return ma, ba
        nb, db, mb = sums(rows_b)
        bb = (W @ nb) / np.maximum(W @ db, 1e-9)
        return ma - mb, ba - bb

    def _s45_tw(self, x, rows_a, rows_b=None, B=2000):
        """two-way (security x date) bootstrap CI of the same statistic"""
        nsec = int(self.SID.max()) + 1
        du = np.unique(self.D)
        W1 = self._boot_W(B, 4502, nsec); W2 = self._boot_W(B, 4503, len(du))
        def prep(rows):
            v = x[rows]; f = np.isfinite(v)
            return v[f], self.SID[rows][f], np.searchsorted(du, self.D[rows][f])
        va, sa, da = prep(rows_a)
        if rows_b is not None:
            vb, sb, db = prep(rows_b)
        out = np.empty(B)
        for i in range(B):
            wa = W1[i][sa] * W2[i][da]
            m = (wa * va).sum() / max(wa.sum(), 1e-9)
            if rows_b is not None:
                wb = W1[i][sb] * W2[i][db]
                m -= (wb * vb).sum() / max(wb.sum(), 1e-9)
            out[i] = m
        return out

    def _s45_dline(self, rows):
        po = lambda c: self.PO[rows, PI45[c]].astype(np.float64)
        b5, b10, l10, l5 = po("B5"), po("B10"), po("L10"), po("L5")
        f = lambda a: a[np.isfinite(a)]
        sh = lambda a, t: 100 * np.mean(f(a) <= t) if len(f(a)) else np.nan
        return (f"n {len(rows)} | B1/B3/B5/B10 med {np.nanmedian(100 * po('B1')):.1f}/{np.nanmedian(100 * po('B3')):.1f}/{np.nanmedian(100 * b5):.1f}/{np.nanmedian(100 * b10):.1f}%"
                f" B5 p10/25/75/90 {q(100 * f(b5), (10, 25, 75, 90))}% | L1/L3/L5/L10 med {np.nanmedian(100 * po('L1')):.1f}/{np.nanmedian(100 * po('L3')):.1f}/{np.nanmedian(100 * l5):.1f}/{np.nanmedian(100 * l10):.1f}%"
                f" | touch L10<= -5/-10/-20/-30/-50 {sh(l10, -.05):.0f}/{sh(l10, -.1):.0f}/{sh(l10, -.2):.0f}/{sh(l10, -.3):.0f}/{sh(l10, -.5):.0f}%"
                f" | B5<= -10/-20/-30/-50 {sh(b5, -.1):.1f}/{sh(b5, -.2):.1f}/{sh(b5, -.3):.1f}/{sh(b5, -.5):.1f}% B10 {sh(b10, -.1):.1f}/{sh(b10, -.2):.1f}/{sh(b10, -.3):.1f}/{sh(b10, -.5):.1f}%"
                f" | dd5/dd10 med {np.nanmedian(100 * po('dd5')):.1f}/{np.nanmedian(100 * po('dd10')):.1f}% | A10 med {np.nanmedian(100 * po('A10')):.1f}% | t(min L)/t(max H) med {np.nanmedian(po('tmin10')):.0f}/{np.nanmedian(po('tmax10b')):.0f}")

    def _s45_payoff(self, rows, cost):
        code = self.FCA[rows, FCI[(0.3, 0.1, 5)]]
        b5 = self.PO[rows, PI45["B5"]].astype(np.float64)
        pay = np.where(code == 1, 0.30, np.where((code == 2) | (code == 3), -0.10, np.where(code == 0, b5, np.nan)))
        return pay - cost

    def mode_s45outcome(self):
        S = self.set_runtime_statistic
        self._s45_finish()
        if S30 is None:
            S("ERR cost", "S30 not set: S45OUTCOME must run after the cost amendment (protocol 8)")
            self._s45_end()
            return
        costs = {"optimistic": 1.0 * S30 + 0.001, "neutral": 2.0 * S30 + 0.005, "conservative": 3.0 * S30 + 0.015}
        exante, lab, st, mv, eh = self._s45_primary()
        sc = self._s45_models(exante, lab, st, eh, [("STATE", "state", []), ("L2_FULL", "l2", FULL45)], folds=("a", "b"))
        test = (self.D >= T0) & (self.D <= T1)
        popev = exante & np.isfinite(sc["L2_FULL"]) & test
        sig = {nm: self._s45_signals(sc[nm], popev, 0.10) for nm in ("STATE", "L2_FULL")}
        G = {"G0 uncond S1": np.nonzero(st["umask"] & test)[0], "G1 S1-P5 pop": np.nonzero(popev)[0],
             "G2 STATE sig": np.nonzero(sig["STATE"])[0], "G3 L2 sig": np.nonzero(sig["L2_FULL"])[0]}
        S("O0 groups (2021-25)", " | ".join(f"{k}: rows {len(v)} secs {len(np.unique(self.SID[v]))}" for k, v in G.items())[:198])
        nsec = int(self.SID.max()) + 1
        W = self._boot_W(2000, 4501, nsec)
        g1, g2, g3 = G["G1 S1-P5 pop"], G["G2 STATE sig"], G["G3 L2 sig"]
        per = {t: (self.D >= lo) & (self.D <= hi) for t, (lo, hi) in (("21-22", P21), ("23-25", P23))}
        # family tables with BH within family (G3 vs G1)
        for fam, names in self._s45_fam().items():
            res = []
            for nm in names:
                x = self._s45_tgt(nm)
                d0, bd = self._s45_gb(x, g3, g1, W, nsec)
                p3, p1, p2 = np.nanmean(x[g3]), np.nanmean(x[g1]), np.nanmean(x[g2])
                res.append((nm, p3, p1, p2, self._pval(bd)))
            ps = np.array([r[4] for r in res]); o = np.argsort(ps); qv = np.empty(len(ps)); mn = 1.0
            for r in range(len(ps) - 1, -1, -1):
                mn = min(mn, ps[o[r]] * len(ps) / (r + 1)); qv[o[r]] = mn
            self.lg(f"FAM {fam} (P G3 L2 / G1 pop / G2 STATE %, lift G3/G1, BH q): " + " | ".join(f"{r[0]} {100 * r[1]:.2f}/{100 * r[2]:.2f}/{100 * r[3]:.2f} x{r[1] / max(r[2], 1e-9):.2f} q{qq:.3f}" for r, qq in zip(res, qv)))
            nsig = int((qv < 0.05).sum()); best = max(res, key=lambda r: r[1] / max(r[2], 1e-9))
            S(f"O1 family {fam}", f"targets {len(res)} | BH q<0.05 (G3 vs pop): {nsig} | best lift {best[0]} {100 * best[1]:.2f}% vs {100 * best[2]:.2f}% x{best[1] / max(best[2], 1e-9):.2f}")
        # family C outcome composition for the primary bracket and the short list
        c4 = {}
        for nm in SHORT:
            x = self._s45_tgt(nm)
            p3, p1 = np.nanmean(x[g3]), np.nanmean(x[g1])
            d0, bd = self._s45_gb(x, g3, g1, W, nsec)
            dS, bS = self._s45_gb(x, g3, g2, W, nsec)
            lifts = {}
            for t, m in per.items():
                a, b = np.nanmean(x[g3[m[g3]]]), np.nanmean(x[g1[m[g1]]])
                lifts[t] = a / max(b, 1e-9)
            if nm.startswith("FC"):
                h, u, d = (int(v) for v in nm[2:].split("_"))
                code = self.FCA[g3, FCI[(u / 100, d / 100, h)]]
                val = code >= 0
                ps_, pa_, pam = (code[val] == 1).mean(), (code[val] == 2).mean(), (code[val] == 3).mean()
                adv_ok = ps_ > pa_ + pam
                succ = g3[code == 1]
                conf = (self.PO[succ, PI45[f"M{h}"]] >= u / 100 - 1e-12).mean() if len(succ) else np.nan
                conf_ok = conf >= 0.5
                extra = f"succ {100 * ps_:.2f}% adv {100 * pa_:.2f}% amb {100 * pam:.2f}% neither {100 * (code[val] == 0).mean():.1f}% | close-conf {100 * conf:.0f}%"
            else:
                h, t_ = (int(v) for v in nm[2:].split("_"))
                lo_ = self.PO[g3, PI45[f"L{h}"]].astype(np.float64)
                padv = np.nanmean(np.where(np.isfinite(lo_), lo_ <= -t_ / 100, np.nan))
                adv_ok = p3 > padv
                conf_ok = True
                extra = f"P(L{h}<=-{t_}%) {100 * padv:.2f}%"
            ok = (p3 >= 1.5 * p1) and (np.percentile(bd, 2.5) > 0) and all(v >= 1.2 for v in lifts.values()) and adv_ok and conf_ok
            c4[nm] = ok
            S(f"C4 {nm}", (f"P {100 * p3:.2f}% base {100 * p1:.2f}% x{p3 / max(p1, 1e-9):.2f} d {self._ci(100 * bd, 2)} | vs STATE {100 * dS:+.2f}{self._ci(100 * bS, 2)} | lift 21-22 {lifts['21-22']:.2f} 23-25 {lifts['23-25']:.2f}"
                              f" | {extra} -> {'PASS' if ok else 'fail'}")[:198])
        x = self._s45_tgt("FC5_30_10")
        bt = self._s45_tw(x, g3, g1)
        S("C4 verdict", f"short-list targets passing: {[k for k, v in c4.items() if v]} -> C4 {'PASS' if any(c4.values()) else 'FAIL'} | FC5_30_10 two-way CI of P-base {self._ci(100 * bt, 2)}")
        # C5 downside of the timing signals
        m5 = self.PO[g3, PI45["M5"]].astype(np.float64); l5 = self.PO[g3, PI45["L5"]].astype(np.float64); b5 = self.PO[g3, PI45["B5"]].astype(np.float64)
        pu, pd_ = np.nanmean(np.where(np.isfinite(m5), m5 >= 0.2, np.nan)), np.nanmean(np.where(np.isfinite(l5), l5 <= -0.2, np.nan))
        med5 = np.nanmedian(b5); p30 = np.nanmean(np.where(np.isfinite(b5), b5 <= -0.3, np.nan))
        c5 = (pu > pd_) and (med5 >= 0) and (p30 <= 0.05)
        S("C5 downside (G3)", f"P(M5>=20%) {100 * pu:.2f}% vs P(L5<=-20%) {100 * pd_:.2f}% | median B5 {100 * med5:+.2f}% | P(B5<=-30%) {100 * p30:.2f}% -> C5 {'PASS' if c5 else 'FAIL'}")
        for k, v in G.items():
            self.lg(f"DOWN {k}: " + self._s45_dline(v))
            S(f"O2 downside {k}", self._s45_dline(v)[:198])
        # success vs failure on the primary bracket (timing signals)
        code = self.FCA[g3, FCI[(0.3, 0.1, 5)]]
        xr = self.OUT[:, OI["xr"]]
        parts = []
        for lab_, m in (("success", code == 1), ("adverse", code == 2), ("ambiguous", code == 3), ("neither", code == 0), ("incomplete", code < 0)):
            r = g3[m]
            if len(r) == 0:
                parts.append(f"{lab_} 0"); continue
            parts.append(f"{lab_} {len(r)}: px {np.median(self.RC[r]):.2f} dvmed {np.median(self.DVMED[r]) / 1e3:.0f}k xr {100 * np.nanmedian(xr[r]):.0f}% B10 {100 * np.nanmedian(self.PO[r, PI45['B10']]):+.0f}%")
        self.lg("SPLIT FC5_30_10 (G3): " + " | ".join(parts))
        S("O3 FC5_30_10 split (G3)", " | ".join(p.split(":")[0] for p in parts)[:198])
        # C7 payoff proxy
        same1 = np.concatenate([[False], self.GS[1:] == self.GS[:-1]])
        s3 = sig["L2_FULL"]
        recent = np.zeros(len(s3), dtype=bool)
        for k in range(1, 6):
            sh = np.zeros(len(s3), dtype=bool); sh[k:] = s3[:-k]
            ok = np.ones(len(s3), dtype=bool); ok[k:] = self.GS[k:] == self.GS[:-k]; ok[:k] = False
            recent |= sh & ok
        g3d = np.nonzero(s3 & ~recent)[0]
        c7 = None
        for scen, cst in costs.items():
            pay = self._s45_payoff(np.arange(len(self.D)), cst)
            m3, b3 = self._s45_gb(pay, g3, None, W, nsec)
            mS, bS_ = self._s45_gb(pay, g2, None, W, nsec)
            m1, b1 = self._s45_gb(pay, g1, None, W, nsec)
            md, bdd = self._s45_gb(pay, g3d, None, W, nsec)
            pp = {t: np.nanmean(pay[g3[m[g3]]]) for t, m in per.items()}
            line = (f"cost {100 * cst:.2f}% | G3 mean {100 * m3:+.2f}% {self._ci(100 * b3, 2)} | dedup5 {100 * md:+.2f}% {self._ci(100 * bdd, 2)} | STATE {100 * mS:+.2f}% pop {100 * m1:+.2f}%"
                    f" | 21-22 {100 * pp['21-22']:+.2f} 23-25 {100 * pp['23-25']:+.2f}")
            if scen == "neutral":
                bt = self._s45_tw(pay, g3)
                c7 = np.percentile(b3, 2.5) > 0
                line += f" | two-way {self._ci(100 * bt, 2)}"
            S(f"C7 payoff {scen}", line[:198])
        nexc = int((self.FCA[g3, FCI[(0.3, 0.1, 5)]] < 0).sum())
        S("C7 verdict", f"neutral security-bootstrap CI lower bound > 0: {'PASS' if c7 else 'FAIL'} | incomplete excluded {nexc} of {len(g3)} | gross outcome per row, overlapping signals counted (not a simulation)")
        # Amendment 4 (exploratory, added after S45MODEL; no criterion): strict pre-move population xr(t) < 50 %, re-ranked
        strict = popev & (np.nan_to_num(xr, nan=0) < 0.5)
        gs = np.nonzero(self._s45_signals(sc["L2_FULL"], strict, 0.10))[0]; gp = np.nonzero(strict)[0]
        fx = self._s45_tgt("FC5_30_10"); cbx = self._s45_tgt("CB5_50")
        dS_, bS2 = self._s45_gb(fx, gs, gp, W, nsec)
        payn = self._s45_payoff(np.arange(len(self.D)), costs["neutral"])
        mN, bN = self._s45_gb(payn, gs, None, W, nsec)
        b5s = self.PO[gs, PI45["B5"]].astype(np.float64); l5s = self.PO[gs, PI45["L5"]].astype(np.float64)
        S("X7 strict pre-move G3 (xr<50%, exploratory)", (f"signals {len(gs)} pop {len(gp)} | FC5_30_10 {100 * np.nanmean(fx[gs]):.2f}% vs {100 * np.nanmean(fx[gp]):.2f}% d {self._ci(100 * bS2, 2)} | CB5_50 {100 * np.nanmean(cbx[gs]):.2f}%"
                                                          f" | med B5 {100 * np.nanmedian(b5s):+.2f}% P(L5<=-20%) {100 * np.nanmean(np.where(np.isfinite(l5s), l5s <= -0.2, np.nan)):.1f}% | neutral payoff {100 * mN:+.2f}% {self._ci(100 * bN, 2)}")[:198])
        # Family A vs B/C capture (timing signals)
        a5 = self._s45_tgt("A5_50"); cb = self._s45_tgt("CB5_50"); fc = self._s45_tgt("FC5_50_15")
        hitA = g3[a5[g3] == 1]
        S("O4 Family A vs B-max / C (G3)", f"A5>=+50% {100 * np.nanmean(a5[g3]):.2f}% | of those also CB5_50 {100 * np.nanmean(cb[hitA]):.0f}% FC5_50_15 {100 * np.nanmean(fc[hitA]):.0f}% | CB5_50 {100 * np.nanmean(cb[g3]):.2f}% FC5_50_15 {100 * np.nanmean(fc[g3]):.2f}%")
        # S2 direction of C4 (lift > 1 for the short list)
        self._s45_free()
        ex2, lab2, st2 = self._s45_pop("S2", 0.05, "E1", 3, "trail")
        sc2 = self._s45_models(ex2, lab2, st2, eh, [("L2_FULL", "l2", FULL45)], folds=("a", "b"))["L2_FULL"]
        pe2 = ex2 & np.isfinite(sc2) & test
        s2 = np.nonzero(self._s45_signals(sc2, pe2, 0.10))[0]; p2r = np.nonzero(pe2)[0]
        parts = []
        for nm in SHORT:
            x = self._s45_tgt(nm)
            parts.append(f"{nm} x{np.nanmean(x[s2]) / max(np.nanmean(x[p2r]), 1e-9):.2f}")
        S("C6 part: S2 lifts of the C4 short list", (f"S2-P5 signals {len(s2)} pop {len(p2r)} | " + " ".join(parts))[:198])
        self.lg("S2 DOWN G3: " + self._s45_dline(s2))
        self._s45_end()
