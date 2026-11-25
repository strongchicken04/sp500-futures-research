# region imports
from AlgorithmImports import *
from datetime import date as _date, timedelta
import hashlib, re, bisect, math, time as _time
import numpy as np
import pandas as pd
from xup_s3_const import *
# endregion


class ModesAB:
    # ---------------- MODE: AUDIT ----------------
    def mode_audit(self):
        S = self.set_runtime_statistic
        D, F, L = self.D, self.F, self.L
        cc = {}
        for sid in self.cls_all.values():
            cc[sid] = cc.get(sid, 0) + 1
        S("A0 classes (all securities)", " ".join(f"{k} {v}" for k, v in sorted(cc.items(), key=lambda kv: -kv[1]))[:198])
        prim = L[:, PRIMARY]
        for u, m in self.U.items():
            v = m & (prim >= 0)
            S(f"A1 {u}", f"securities {len(np.unique(self.SID[m]))} | eligible rows {int(m.sum())} | primary-label valid {int(v.sum())} events {int((prim[v] == 1).sum())} rate {100.0 * (prim[v] == 1).mean() if v.any() else 0:.3f}%")
        # feature coverage and quantiles (log lines)
        self.lg("FEATURE COVERAGE (share finite on A rows / within the feature's universe) and p1 p50 p99")
        for k, nm in enumerate(FEATS):
            col = F[:, k]
            fin = np.isfinite(col)
            q = np.nanpercentile(col[fin], [1, 50, 99]) if fin.any() else [np.nan] * 3
            self.lg(f"{nm}: {100.0 * fin.mean():.1f}% | {q[0]:.4g} {q[1]:.4g} {q[2]:.4g}")
        # label validity
        inv = [(nm, 100.0 * (L[:, i] < 0).mean()) for nm, i in (("A5", TI[("A", 5, 1.0)]), ("A10", PRIMARY), ("A20", TI[("A", 20, 1.0)]))]
        S("A2 invalid (incomplete) label share", " ".join(f"{a} {b:.2f}%" for a, b in inv))
        # SI match: sampled A securities alive in 2019 with any SI record
        alive19 = [sid for sid in self.sid_list if self.first[sid] <= _date(2019, 6, 1) <= self.last[sid]]
        S("A3 SI match", f"sampled A securities alive mid-2019 {len(alive19)} with SI records {sum(1 for s in alive19 if s in self.si)} | D rows {int(self.U['D'].sum())}")
        # leakage unit test: recompute features with data truncated at t for random (security, t)
        rng = np.random.RandomState(11)
        picks = rng.choice(len(self.sid_list), size=min(12, len(self.sid_list)), replace=False)
        worst = 0.0
        tested = 0
        for pi in picks:
            sid = self.sid_list[pi]
            s = self.syms[sid]
            fa = self._hist([s], DataNormalizationMode.ADJUSTED).get(s)
            fr = self._hist([s], DataNormalizationMode.RAW).get(s)
            full = self._security(sid, self.cls_all[sid], fa, fr)
            if full is None or len(full[0]) < 100:
                continue
            for q in (0.3, 0.7):
                t = full[0][int(q * (len(full[0]) - 1))]
                cut_a = tuple(x[fa[0] <= t] for x in fa)
                cut_r = tuple(x[fr[0] <= t] for x in fr)
                part = self._security(sid, self.cls_all[sid], cut_a, cut_r)
                if part is None:
                    continue
                i_full = int(np.nonzero(full[0] == t)[0][0])
                if t not in part[0]:
                    continue
                i_part = int(np.nonzero(part[0] == t)[0][0])
                a, b = full[1][i_full], part[1][i_part]
                both = np.isfinite(a) & np.isfinite(b)
                diff = float(np.max(np.abs(a[both] - b[both]))) if both.any() else 0.0
                nanmis = int(np.sum(np.isfinite(a) != np.isfinite(b)))
                worst = max(worst, diff + nanmis)
                tested += 1
        S("A4 leakage unit test", f"{tested} (security, t) pairs: max |feature(full data) - feature(data cut at t)| + NaN mismatches = {worst:.3g}")
        # eligible rows by block and universe
        self.lg("ELIGIBLE ROWS / PRIMARY EVENTS BY BLOCK")
        for u, m in self.U.items():
            parts = []
            for bi, (a, b) in enumerate(BLOCKS):
                mm = m & (self.BL == bi) & (L[:, PRIMARY] >= 0)
                parts.append(f"{a}-{b % 100:02d}: {int(mm.sum())}/{int((L[mm, PRIMARY] == 1).sum())}")
            self.lg(f"{u}: " + " | ".join(parts))
        S("A5 runtime", f"{(_time.time() - self.t0) / 60:.0f} min total")

    # ---------------- shared helpers ----------------
    def _month(self):
        if not hasattr(self, "MO"):
            u = np.unique(self.D)
            mo = np.array([(_date.fromordinal(int(x)).year - 2000) * 12 + _date.fromordinal(int(x)).month for x in u], dtype=np.int16)
            self.MO = mo[np.searchsorted(u, self.D)]
        return self.MO

    def _episodes(self, rows_mask, li, h):
        """non-overlapping episodes among positive rows (row order = security, date)"""
        idx = np.nonzero(rows_mask & (self.L[:, li] == 1))[0]
        if len(idx) == 0:
            return 0, 0
        sid = self.SID[idx]
        ep, last_sid, last_i = 0, -1, -10 ** 9
        for i, s in zip(idx, sid):
            if s != last_sid or i - last_i >= h:
                ep += 1
                last_i = i
                last_sid = s
        return ep, len(np.unique(sid))

    # ---------------- MODE: BASE (Stage 3B) ----------------
    def mode_base(self):
        S = self.set_runtime_statistic
        L, F, R = self.L, self.F, self.R
        prim = L[:, PRIMARY]
        pstrat = F[:, FI["pstrat"]]
        miss = F[:, FI["miss20"]]
        for u, m in self.U.items():
            v = m & (prim >= 0)
            pos = v & (prim == 1)
            ep, ns = self._episodes(v, PRIMARY, 10)
            rr = R[pos]
            med = np.nanmedian(rr) * 100 if len(rr) else np.nan
            p90 = np.nanpercentile(rr, 90) * 100 if len(rr) else np.nan
            st = [100.0 * np.mean(pstrat[pos] == k) if pos.any() else 0 for k in (0, 1, 2)]
            inc = 100.0 * np.mean(prim[m] < 0) if m.any() else 0
            ms = 100.0 * np.mean(miss[pos] == 1) if pos.any() else 0
            S(f"B1 {u} primary all years", f"secs {len(np.unique(self.SID[m]))} rows {int(m.sum())} valid {int(v.sum())} pos {int(pos.sum())} rate {100.0 * pos.sum() / max(1, v.sum()):.3f}% | ev secs {ns} ep {ep} | ret med {med:.0f}% p90 {p90:.0f}% | <$1 {st[0]:.0f}% 1-5 {st[1]:.0f}% >5 {st[2]:.0f}% | incompl {inc:.2f}% miss20 {ms:.0f}%"[:198])
            parts = []
            for bi, (a, b) in enumerate(BLOCKS):
                vv = v & (self.BL == bi)
                parts.append(f"{a % 100:02d}-{b % 100:02d} {100.0 * (prim[vv] == 1).sum() / max(1, vv.sum()):.3f}% ({int((prim[vv] == 1).sum())}/{int(vv.sum() / 1000)}k)")
            S(f"B2 {u} primary by block", " | ".join(parts)[:198])
            # detailed block lines -> log
            for bi, (a, b) in enumerate(BLOCKS):
                mm = m & (self.BL == bi)
                vv = mm & (prim >= 0)
                pp = vv & (prim == 1)
                ep, ns = self._episodes(vv, PRIMARY, 10)
                st = [100.0 * np.mean(pstrat[pp] == k) if pp.any() else 0 for k in (0, 1, 2)]
                self.lg(f"{u} {a}-{b}: secs {len(np.unique(self.SID[mm]))} rows {int(mm.sum())} valid {int(vv.sum())} pos {int(pp.sum())} rate {100.0 * pp.sum() / max(1, vv.sum()):.3f}% evsecs {ns} ep {ep} med {np.nanmedian(R[pp]) * 100 if pp.any() else 0:.0f}% p90 {np.nanpercentile(R[pp], 90) * 100 if pp.any() else 0:.0f}% strata {st[0]:.0f}/{st[1]:.0f}/{st[2]:.0f} inc {100.0 * np.mean(prim[mm] < 0) if mm.any() else 0:.2f}% miss {100.0 * np.mean(miss[pp] == 1) if pp.any() else 0:.0f}%")
        # all 27 targets for A by block (rate %)
        mA = self.U["A"]
        for f in ("A", "B", "M"):
            for h in HZ:
                parts = []
                for t in TH:
                    li = TI[(f, h, t)]
                    rates = []
                    for bi in range(len(BLOCKS)):
                        vv = mA & (self.BL == bi) & (L[:, li] >= 0)
                        rates.append(f"{100.0 * (L[vv, li] == 1).sum() / max(1, vv.sum()):.3f}")
                    parts.append(f"+{int(t * 100)} " + "/".join(rates))
                S(f"B3 A {f}{h} rate% by block", " | ".join(parts)[:198])
        # all 27 targets overall for the other universes (log)
        self.lg("ALL TARGETS, ALL YEARS: rate% (positives) per universe")
        for u, m in self.U.items():
            parts = []
            for (f, h, t) in TGT:
                li = TI[(f, h, t)]
                vv = m & (L[:, li] >= 0)
                parts.append(f"{f}{h}/{int(t * 100)} {100.0 * (L[vv, li] == 1).sum() / max(1, vv.sum()):.3f}({int((L[vv, li] == 1).sum())})")
            self.lg(f"{u}: " + " ".join(parts))
        # price strata and liquidity regimes x block, A, primary
        ldv = F[:, FI["ldv"]]
        dvb = np.select([ldv < np.log1p(1e5), ldv < np.log1p(1e6), ldv < np.log1p(1e7)], [0, 1, 2], 3)
        for nm, arr, labs in (("price", pstrat, ("<1", "1-5", ">5")), ("dollar vol", dvb, ("<100k", "100k-1M", "1-10M", ">10M"))):
            for k, lab in enumerate(labs):
                parts = []
                for bi, (a, b) in enumerate(BLOCKS):
                    vv = mA & (self.BL == bi) & (prim >= 0) & (arr == k)
                    parts.append(f"{a % 100:02d}: {100.0 * (prim[vv] == 1).sum() / max(1, vv.sum()):.3f}%/{int(vv.sum() / 1000)}k")
                S(f"B4 A {nm} {lab}", " | ".join(parts)[:198])

