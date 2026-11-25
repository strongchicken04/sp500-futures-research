# region imports
from AlgorithmImports import *
from datetime import date as _date
import numpy as np
import pandas as pd
from xup_s3_const import *
from xup_s3_modes_m import SPECS, _split
from xup_s4_core import *
# endregion
#
# Stage 4A (reproducibility audit, Stage 3 discrepancy) and Stage 4B (event populations).


class S4ModesA:

    def _s3_trad_line(self, se, evm):
        """Stage 3 _tradability formula (top 1 % within day, S3-rank) for any score vector"""
        pr = self._dayrank(se, self.D[evm])
        sel = np.nonzero(evm)[0][pr <= 0.01]
        F = self.F
        px = np.exp(F[sel, FI["lpx"]]); dv = np.expm1(F[sel, FI["ldv"]])
        y = self.L[sel, PRIMARY] == 1
        b = self.L[sel, TI[("B", 10, 1.0)]] == 1; bm = self.L[sel, TI[("M", 10, 1.0)]] == 1
        return (f"rows {len(sel)} events {int(y.sum())} | px med {np.nanmedian(px):.2f} <$1 {100 * np.mean(px < 1):.0f}% 1-5 {100 * np.mean((px >= 1) & (px < 5)):.0f}% | $vol med {np.nanmedian(dv) / 1e3:.0f}k <100k {100 * np.mean(dv < 1e5):.0f}%"
                f" | miss20 {100 * np.mean(F[sel, FI['miss20']] == 1):.0f}% | conf B {100 * b[y].mean() if y.any() else 0:.0f}% Bmax {100 * bm[y].mean() if y.any() else 0:.0f}% | ret>200% {100 * np.mean(self.R[sel][y] > 2) if y.any() else 0:.0f}%")

    def mode_s4audit(self):
        S = self.set_runtime_statistic
        self._s4_finish()
        prim = self.L[:, PRIMARY]
        tr, te, ytd = _split(self, "std", True)
        evm = self.U["A"] & te & (prim >= 0)
        allte = self.U["A"] & te
        S("A0 test rows", f"2021-2025 A eligible rows {int(allte.sum())} | valid primary labels {int(evm.sum())} | invalid {int((allte & (prim < 0)).sum())} | positives {int((evm & (prim == 1)).sum())} | base {100 * (prim[evm] == 1).mean():.3f}%")
        ep, ns = self._episodes(self.U["A"] & (prim >= 0), PRIMARY, 10)
        S("A0 episodes", f"E1 all years (Stage 3 BASE: 4207 episodes / 1159 securities): {ep} / {ns}")
        ye = (prim[evm] == 1).astype(int)
        sc = {}
        for nm in ("fullA RF", "volume LR", "fullA GBM", "price LR", "momentum LR", "fullA LR"):
            f, cols = self._s4_fit(nm, True)
            se = f(self.F[evm][:, cols])
            sc[nm] = se
            mt = self._metrics(se, ye, self.D[evm], self.SID[evm])
            S(f"A1 {SHORT[nm]} S3-rank", (f"PR-AUC {mt['ap']:.4f} {mt['ap_ci'][0]:.4f}-{mt['ap_ci'][1]:.4f} | P@1 {mt['p1'] * 100:.2f}% ({mt['k1']}/{mt['n1']}) P@5 {mt['p5'] * 100:.2f}% ({mt['k5']}/{mt['n5']})"
                                          f" P@10 {mt['p10'] * 100:.2f}% ({mt['k10']}/{mt['n10']}) | R@1/5/10 {mt['r1'] * 100:.1f}/{mt['r5'] * 100:.1f}/{mt['r10'] * 100:.1f}% | n {mt['n']} pos {mt['pos']} AUC {mt['auc']:.4f}")[:198])
        for nm in ("fullA RF", "fullA GBM", "volume LR"):
            S(f"A2 S3 tradability formula {SHORT[nm]}", self._s3_trad_line(sc[nm], evm)[:198])
        # Stage 4 ranking (all eligible rows ranked, label validity ignored) vs Stage 3 ranking
        scores = self._s4_score(["fullA RF", "volume LR"], True, T0, T1)
        for nm in ("fullA RF", "volume LR"):
            fl, pr = self._s4_flags(scores[nm], allte)
            parts = []
            for k in (0.01, 0.05, 0.10):
                f = fl[k]
                nsel = int(f.sum()); nval = int((f & (prim >= 0)).sum()); npos = int((f & (prim == 1)).sum())
                parts.append(f"top{int(k * 100)}: sel {nsel} valid {nval} pos {npos} P {100 * npos / max(nval, 1):.2f}%")
            S(f"A3 {SHORT[nm]} S4-rank", " | ".join(parts)[:198])
        # rows whose ranking set differs: invalid-label rows by day
        inval = allte & (prim < 0)
        S("A3 invalid rows in ranking", f"test rows with invalid primary label {int(inval.sum())} ({100 * inval.sum() / max(allte.sum(), 1):.2f}%) on {len(np.unique(self.D[inval]))} days; S4-rank includes them, S3-rank does not")
        # reproducibility of the score vectors: refit twice must give identical scores
        f2, cols = self._s4_fit("volume LR", True, cache=False)
        d = np.nanmax(np.abs(f2(self.F[evm][:, cols]) - sc["volume LR"]))
        S("A4 refit determinism", f"volume LR refit max |score diff| {d:.3g}; RF uses random_state 7, n_jobs 1 (deterministic); TEST v1 vs ROBUST v1 point estimates identical")
        self.lg("A5 " + self.s4_check)

    def mode_s4events(self):
        S = self.set_runtime_statistic
        self._s4_finish()
        prim = self.L[:, PRIMARY]
        blocks = [(2006, 2009), (2010, 2014), (2015, 2019), (2020, 2022), (2023, 2025), (2026, 2026)]
        evs = {}
        for fam in ("A", "B", "M"):
            li = TI[(fam, 10, 1.0)]
            for rule in (("E1", "E2") if fam != "A" else ("E1", "E2", "E3")):
                ev = self._s4_events(li, rule)
                evs[(fam, rule)] = ev
                n = len(ev["start"])
                dur = ev["last"] - ev["start"] + 1
                # overlap: next event of the same security starts within h sessions after this event's last row
                nxt = np.append(ev["start"][1:], 10 ** 12)
                same = np.append(ev["sid"][1:] == ev["sid"][:-1], False)
                ovl = same & (nxt <= ev["last"] + 10)
                te = (ev["date"] >= T0) & (ev["date"] <= T1)
                cnf = f" | close-conf B {100 * ev['confB'].mean():.0f}% Bmax {100 * ev['confM'].mean():.0f}%" if fam == "A" and rule != "E3" else ""
                S(f"B1 {fam}10/100 {rule}", (f"events {n} secs {len(np.unique(ev['sid']))} pos-days {int(ev['npos'].sum())} per event mean {ev['npos'].mean():.2f} med {np.median(ev['npos']):.0f}"
                                            f" | dur mean {dur.mean():.1f} med {np.median(dur):.0f} p90 {np.percentile(dur, 90):.0f} | overlap {int(ovl.sum())} | incompl {int(ev['incomplete'].sum())} | test {int(te.sum())}{cnf}")[:198])
                byb = " ".join(f"{a % 100:02d}-{b % 100:02d}:{int(((ev['year'] >= a) & (ev['year'] <= b)).sum())}" for a, b in blocks)
                pxs = np.bincount(self._strata_px(ev["px"]), minlength=7)
                dvs = np.bincount(self._strata_dv(ev["dv"]), minlength=6)
                tes = te
                pxt = np.bincount(self._strata_px(ev["px"][tes]), minlength=7)
                dvt = np.bincount(self._strata_dv(ev["dv"][tes]), minlength=6)
                self.lg(f"{fam}{rule} blocks {byb} | price all {'/'.join(map(str, pxs))} test {'/'.join(map(str, pxt))} | $vol all {'/'.join(map(str, dvs))} test {'/'.join(map(str, dvt))}")
        # E1 ambiguity (episodes that E2 merges with a neighbour) and E3 vs E1 overlap
        e1, e2, e3 = evs[("A", "E1")], evs[("A", "E2")], evs[("A", "E3")]
        rowE2 = np.full(len(self.D), -1, dtype=np.int64)
        for k in range(len(e2["start"])):
            rowE2[e2["start"][k]:e2["last"][k] + 1] = k
        m2 = rowE2[e1["start"]]
        cnt = np.bincount(m2[m2 >= 0], minlength=len(e2["start"]))
        amb = (m2 >= 0) & (cnt[np.maximum(m2, 0)] > 1)
        S("B2 E1 ambiguity", f"E1 episodes merged by E2 with a neighbour {int(amb.sum())} of {len(e1['start'])} ({100 * amb.mean():.1f}%); E2 events built from >1 E1 episode {int((cnt > 1).sum())} of {len(e2['start'])}")
        # E3 move day inside an E1 episode's span [start, last + 10] of the same security segment
        cover = np.zeros(len(self.D), dtype=bool)
        for k in range(len(e1["start"])):
            cover[e1["start"][k]:min(e1["last"][k] + 10, self.SEG1[e1["last"][k]]) + 1] = True
        e3in = cover[e3["start"]]
        xday = np.zeros(len(self.D), dtype=bool)
        xday[np.nonzero(self.OUT[:, OI["xr"]] >= 1.0)[0]] = True
        cx = np.concatenate([[0], np.cumsum(xday)])
        hi = np.minimum(e1["last"] + 10, self.SEG1[e1["last"]])
        e1x = (cx[hi + 1] - cx[e1["start"] + 1]) > 0
        S("B3 E3 vs E1", f"E3 events whose move day lies in an E1 span {int(e3in.sum())}/{len(e3['start'])} ({100 * e3in.mean():.1f}%); E1 episodes with an excursion day in (start, last+10] {int(e1x.sum())}/{len(e1['start'])} ({100 * e1x.mean():.1f}%)")
        # E3 reference validity and E3 events whose first 10 sessions are incomplete
        xr = self.OUT[:, OI["xr"]]
        S("B4 E3 coverage", f"rows with a defined excursion ratio {int(np.isfinite(xr).sum())} of {len(xr)} ({100 * np.isfinite(xr).mean():.1f}%); excursion days {int(xday.sum())}; test E3 events {int(((e3['date'] >= T0) & (e3['date'] <= T1)).sum())}")
        # positives per event in the test period, Family A
        for rule, ev in (("E1", e1), ("E2", e2)):
            te = (ev["date"] >= T0) & (ev["date"] <= T1)
            S(f"B5 test A {rule}", f"2021-25 events {int(te.sum())} secs {len(np.unique(ev['sid'][te]))} pos-days {int(ev['npos'][te].sum())} med pos/event {np.median(ev['npos'][te]):.0f} max ret med {np.median(ev['mx'][te]) * 100:.0f}% incompl {int(ev['incomplete'][te].sum())}")
        ytd = (e1["date"] >= Y0)
        S("B6 2026 YTD A E1", f"events {int(ytd.sum())} incomplete {int(e1['incomplete'][ytd].sum())} (data end 2026-08-27)")
        self.lg("CHECK " + self.s4_check)

    def mode_s4diag(self):
        """panel fingerprint by year (aggregates only) to diagnose run-to-run differences"""
        S = self.set_runtime_statistic
        self._s4_finish()
        c = getattr(self, "s4_cnt", {})
        spy_days = np.array(sorted(self.mdi.keys()))
        sy = np.array([_date.fromordinal(int(d)).year for d in spy_days])
        S("G0 counts", f"history bars {c.get('bars')} md-dropped {c.get('md_drop')} raw/adj-misaligned dropped {c.get('rawadj_drop')} securities {c.get('secs')} | SPY sessions {len(spy_days)} first {_date.fromordinal(int(spy_days[0]))} last {_date.fromordinal(int(spy_days[-1]))} | errors {len(self.err)}")
        prim = self.L[:, PRIMARY]
        lpx = self.F[:, FI["lpx"]]
        parts = []
        for y in range(2006, 2027):
            m = self.Y == y
            parts.append(f"{y % 100:02d}:{int(m.sum())}/{int((prim[m] == 1).sum())}/{len(np.unique(self.SID[m]))}/{int((sy == y).sum())}/{np.nansum(lpx[m]):.0f}")
        S("G1 rows/pos/secs/spydays/sum-lpx by year a", " ".join(parts[:7])[:198])
        S("G1 rows/pos/secs/spydays/sum-lpx by year b", " ".join(parts[7:14])[:198])
        S("G1 rows/pos/secs/spydays/sum-lpx by year c", " ".join(parts[14:])[:198])
        nb = np.bincount(self.SID)
        S("G2 per-security rows", f"securities {len(nb)} rows p10/50/90 {q(nb, (10, 50, 90))} max {nb.max()} | segments {len(np.unique(self.GS))} | sum D mod 1e6 {int(self.D.astype(np.int64).sum() % 1000000)}")
        self.lg("G3 errors: " + " | ".join(e[:40] for e in self.err[:10]))
