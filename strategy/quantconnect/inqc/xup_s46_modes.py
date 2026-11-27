# region imports
from AlgorithmImports import *
import hashlib, json, time as _time
from datetime import datetime as _dt, timedelta as _td, date as _date
import numpy as np
import pandas as pd
from xup_s3_const import *
from xup_s4_core import *
from xup_s4_core import _o
from xup_s45_core import *
from xup_s46_core import *
# endregion
#
# Stage 4.6 modes: S46AUDIT (frozen counts, groups, coverage; no outcomes), S46MAIN (primary + comparisons + secondary),
# S46ROBUST (S2, 2026), S46SHADOW (prospective logging framework). Aggregates only.

P21 = (T0, _o(2022, 12, 31)); P23 = (_o(2023, 1, 1), T1)
FLDS = ["trig", "same", "okb", "okv", "etype", "pe", "strig", "emin", "code", "gross", "ggap", "hold", "mae", "mfe", "minl", "maxh", "c1", "c3", "c5"]


class S46Modes:

    # ---------------- per-observation engine (inside QC) ----------------
    def _s46_run(self, rows, tlimit_min=200.0):
        n, nv = len(rows), len(VAR46)
        R = {f: np.full((n, nv), np.nan) for f in FLDS}
        R["trig"][:] = 0; R["same"][:] = 0; R["okb"][:] = 0; R["okv"][:] = 0; R["etype"][:] = 0; R["code"][:] = -1
        R["cov"] = np.zeros(n, dtype=bool); R["comp"] = np.zeros(n, dtype=bool); R["why"] = np.array([""] * n, dtype=object)
        R["dv30"] = np.full(n, np.nan); R["qcov"] = np.zeros(n, dtype=bool)
        cache, errs, t0 = {}, {}, _time.time()
        self.s46_timeout = False
        for k, i in enumerate(rows):
            if (_time.time() - t0) / 60 > tlimit_min:
                self.s46_timeout = True
                break
            ok, why = self._s46_complete(i)
            R["comp"][k], R["why"][k] = ok, why
            if i + 1 >= len(self.D) or self.GS[i + 1] != self.GS[i] or not np.isfinite(self.RH[i]):
                R["why"][k] = "window"
                continue
            sym = self.syms.get(self.sid_list[self.SID[i]])
            if sym is None:
                errs["nosym"] = errs.get("nosym", 0) + 1
                continue
            try:
                b = self._s46_minute(sym, self.D[i + 1])
            except Exception as e:
                errs[type(e).__name__] = errs.get(type(e).__name__, 0) + 1
                continue
            if b is None:
                continue
            R["cov"][k] = True
            H = float(self.RH[i])
            trig = []
            for v, var in enumerate(VAR46):
                ms, same, dv30, okb, okv = self._s46_trigger(b, H, var)
                R["dv30"][k] = dv30; R["okb"][k, v] = okb; R["okv"][k, v] = okv
                trig.append((ms, same))
            if not any(t[0] is not None for t in trig):
                continue
            q = None
            try:
                q = self._s46_minute(sym, self.D[i + 1], quote=True)
            except Exception as e:
                errs["q" + type(e).__name__] = errs.get("q" + type(e).__name__, 0) + 1
            R["qcov"][k] = q is not None
            for v, (ms, same) in enumerate(trig):
                if ms is None:
                    continue
                R["trig"][k, v], R["same"][k, v], R["emin"][k, v] = 1, int(same), ms
                pe, et, st, je = self._s46_entry(b, q, ms)
                R["etype"][k, v], R["pe"][k, v], R["strig"][k, v] = et, pe, st
                if not np.isfinite(pe) or je < 0:
                    R["code"][k, v] = 4
                    continue
                if not ok:
                    R["code"][k, v] = 4
                    continue
                try:
                    res = self._s46_bracket(i, sym, b, je, pe, cache)
                except Exception as e:
                    errs["br" + type(e).__name__] = errs.get("br" + type(e).__name__, 0) + 1
                    R["code"][k, v] = 4
                    continue
                for f, val in zip(["code", "gross", "ggap", "hold", "mae", "mfe", "minl", "maxh", "c1", "c3", "c5"], res):
                    R[f][k, v] = val
        R["errs"] = errs; R["mins"] = (_time.time() - t0) / 60; R["done"] = k + 1 if n else 0
        return R

    # ---------------- statistics ----------------
    def _s46_W(self):
        if not hasattr(self, "W46"):
            nsec = int(self.SID.max()) + 1
            du = np.unique(self.D)
            self.W46 = (self._boot_W(2000, 4601, nsec), self._boot_W(2000, 4602, nsec), self._boot_W(2000, 4603, len(du)), du, nsec)
        return self.W46

    def _s46_bm(self, x, rows, two=False):
        """mean of x over rows (NaN dropped) with security-cluster bootstrap replicate means (and two-way)"""
        W, W1, W2, du, nsec = self._s46_W()
        f = np.isfinite(x)
        xs, ss = x[f], self.SID[rows][f]
        if len(xs) == 0:
            return np.nan, np.full(2000, np.nan), None
        bs = (W @ np.bincount(ss, weights=xs, minlength=nsec)) / np.maximum(W @ np.bincount(ss, minlength=nsec).astype(float), 1e-9)
        bt = None
        if two:
            di = np.searchsorted(du, self.D[rows][f])
            bt = np.array([(W1[b][ss] * W2[b][di] * xs).sum() / max((W1[b][ss] * W2[b][di]).sum(), 1e-9) for b in range(2000)])
        return float(xs.mean()), bs, bt

    def _s46_net(self, R, v=0, cost="neutral", mode="primary", grossonly=False):
        g = R["ggap"][:, v] if mode == "gap" else R["gross"][:, v]
        c = 0.0 if grossonly else (2 * R["strig"][:, v] + 0.005 if cost == "qi" else COST46[cost])
        x = g - c
        cc = R["code"][:, v]
        x = np.where((cc >= 0) & (cc <= 3), x, np.nan)
        if mode == "conservative":
            x = np.where(R["trig"][:, v] == 1, np.where(np.isfinite(x), x, -0.10 - (0 if grossonly else COST46[cost])), np.nan)
        return x

    def _s46_desc(self, R, sel, v=0):
        tr = sel & (R["trig"][:, v] == 1)
        cc = R["code"][:, v]
        comp = tr & (cc >= 0) & (cc <= 3)
        n = max(int(comp.sum()), 1)
        sh = {o: 100 * (cc[comp] == j).sum() / n for j, o in enumerate(OUTC[:4])}
        return tr, comp, sh

    def _s46_dedup(self, rows, tr):
        keep = tr.copy()
        last = {}
        for k in np.nonzero(tr)[0]:
            i = rows[k]; s = self.SID[i]
            if s in last and self.GS[last[s]] == self.GS[i] and i - last[s] <= 5:
                keep[k] = False
            else:
                last[s] = i
        return keep

    def _s46_bh(self, ps):
        ps = np.array(ps); o = np.argsort(ps); qv = np.empty(len(ps)); mn = 1.0
        for r in range(len(ps) - 1, -1, -1):
            mn = min(mn, ps[o[r]] * len(ps) / (r + 1)); qv[o[r]] = mn
        return qv

    # ---------------- AUDIT (no outcome is computed) ----------------
    def mode_s46audit(self):
        S = self.set_runtime_statistic
        self._s46_finish()
        hp = None
        g = self._s46_groups()
        hp = self.hp45
        n = {k: int(g[k].sum()) for k in ("pop", "L2", "STATE", "VOLU")}
        ctl, nmiss = self._s46_controls(g)
        S("A0 frozen reproduction", f"pop rows {n['pop']} (S45 49697) | L2 {n['L2']} STATE {n['STATE']} (S45 5492/5492) VOLU {n['VOLU']} | L2 C={hp['l2']} RF leaf={hp['rf']} (S45 0.01/100)")
        L, Sg, V = g["L2"], g["STATE"], g["VOLU"]
        uni = L | Sg | V | ctl
        S("A1 groups", f"overlap L2&STATE {int((L & Sg).sum())} L2&VOLU {int((L & V).sum())} STATE&VOLU {int((Sg & V).sum())} | controls {int(ctl.sum())} (unmatched L2 rows {nmiss}) | union {int(uni.sum())} rows")
        atr = self.F[:, self.FC45["atr_p"]].astype(np.float64)
        bal = []
        for nm, m in (("L2", L), ("CTL", ctl), ("STATE", Sg), ("VOLU", V), ("POP", g["pop"])):
            bal.append(f"{nm} px {np.median(self.RC[m]):.2f} dv {np.median(self.DVMED[m]) / 1e6:.2f}M atr {100 * np.nanmedian(atr[m]):.1f}%")
        S("A2 balance (medians)", " | ".join(bal)[:198])
        # completeness of the daily window (no outcome)
        parts = []
        for nm, m in (("L2", L), ("STATE", Sg), ("CTL", ctl)):
            rr = np.nonzero(m)[0]
            w = [self._s46_complete(i)[1] for i in rr]
            parts.append(f"{nm} complete {sum(1 for x in w if x == '')}/{len(rr)} window {w.count('window')} daily {w.count('daily')} corp {w.count('corp')}")
        S("A3 daily windows t..t+5", " | ".join(parts)[:198])
        # minute / quote coverage audit on hash samples (session t+1 and session t); no trigger or outcome is evaluated
        t0 = _time.time()
        recs = {}
        for nm, m in (("L2", L), ("STATE", Sg), ("CTL", ctl)):
            rr = self._hsel(np.nonzero(m)[0], 80, "a46" + nm)
            out = []
            for i in rr:
                sym = self.syms.get(self.sid_list[self.SID[i]])
                if sym is None or i + 1 >= len(self.D) or self.GS[i + 1] != self.GS[i]:
                    continue
                try:
                    t0h = _dt.combine(_date.fromordinal(int(self.D[i + 1])), _dt.min.time())
                    hr = self.history(sym, t0h, t0h + _td(days=1), Resolution.MINUTE, fill_forward=False, extended_market_hours=False, data_normalization_mode=DataNormalizationMode.RAW)
                    rb = self._s46_df(hr)
                    b = self._s46_minute(sym, self.D[i + 1]); qb = self._s46_minute(sym, self.D[i + 1], quote=True)
                    bt = self._s46_minute(sym, self.D[i])
                    r = {"raw_min": int(rb["m"].min()) if rb is not None and len(rb["m"]) else -1, "raw_max": int(rb["m"].max()) if rb is not None and len(rb["m"]) else -1,
                         "nb": len(b["m"]) if b else 0, "nq": len(qb["m"]) if qb else 0}
                    if qb is not None:
                        a, bd = qb["askclose"], qb["bidclose"]
                        r["qvalid"] = float(np.mean((a > 0) & (bd > 0) & (a >= bd)))
                        r["qsize"] = float(np.mean(np.isfinite(qb["asksize"]) & (qb["asksize"] > 0)))
                        r["q30"] = int((qb["m"] <= 600).sum())
                    if bt is not None:
                        r["hdiff"] = float(bt["high"].max() / self.RH[i] - 1)
                    out.append(r)
                except Exception as e:
                    out.append({"err": type(e).__name__})
            recs[nm] = out
        sec = (_time.time() - t0) / max(sum(len(v) for v in recs.values()), 1)
        for nm, out in recs.items():
            g_ = lambda k: np.array([r.get(k, np.nan) for r in out], dtype=float)
            S(f"A4 coverage {nm}", (f"n {len(out)} errors {sum(1 for r in out if 'err' in r)} | t+1 trade bars {int((g_('nb') > 0).sum())} median {np.nanmedian(g_('nb')):.0f} | quotes {int((g_('nq') > 0).sum())} median {np.nanmedian(g_('nq')):.0f}"
                                    f" first30 {np.nanmedian(g_('q30')):.0f} valid {100 * np.nanmean(g_('qvalid')):.0f}% sizes {100 * np.nanmean(g_('qsize')):.0f}% | dayHigh(min)/dayHigh(daily)-1 p10/50/90 {q(100 * g_('hdiff'), (10, 50, 90))}%")[:198])
        allr = [r for v in recs.values() for r in v]
        mn = np.array([r.get("raw_min", -1) for r in allr]); mx = np.array([r.get("raw_max", -1) for r in allr])
        S("A5 bar labels / hours", f"regular-hours request: earliest bar label 09:30 in {int((mn == 570).sum())}, 09:31 in {int((mn == 571).sum())}; latest 16:00 in {int((mx == 960).sum())}, 15:59 in {int((mx == 959).sum())}; outside 09:30-16:00 {int(((mn >= 0) & (mn < 570)).sum() + (mx > 960).sum())} | shift {self._s46_shift(None)} | {sec:.2f} s per item")
        self._s45_end()

    # ---------------- MAIN ----------------
    def mode_s46main(self):
        S = self.set_runtime_statistic
        self._s46_finish()
        g = self._s46_groups()
        ctl, nmiss = self._s46_controls(g)
        G = {"L2": g["L2"], "STATE": g["STATE"], "VOLU": g["VOLU"], "CTL": ctl}
        uni = g["L2"] | g["STATE"] | g["VOLU"] | ctl
        rows = np.nonzero(uni)[0]
        S("M0 frozen groups", f"pop {int(g['pop'].sum())} | L2 {int(g['L2'].sum())} STATE {int(g['STATE'].sum())} VOLU {int(g['VOLU'].sum())} CTL {int(ctl.sum())} (unmatched {nmiss}) | union {len(rows)} | L2 C={self.hp45['l2']}")
        self._s45_mem("before minute loop")
        R = self._s46_run(rows)
        if self.s46_timeout:
            S("ERR timeout", f"minute loop stopped after {R['mins']:.0f} min at {R['done']}/{len(rows)}")
            self._s45_end()
            return
        S("M1 minute loop", f"rows {len(rows)} done {R['done']} in {R['mins']:.1f} min | history calls {getattr(self, 's46_calls', 0)} | label shift {self._s46_shift(None)} | errors {R['errs'] if R['errs'] else 'none'}"[:198])
        self.R46, self.rows46, self.G46, self.g46 = R, rows, G, g
        self._s46_report("S1 2021-25", rows, R, G, g, full=True)
        self._s45_end()

    def _s46_report(self, tag, rows, R, G, g, full=True):
        S = self.set_runtime_statistic
        mem = {k: m[rows] for k, m in G.items()}
        res = {}
        for nm, sel in mem.items():
            tr, comp, sh = self._s46_desc(R, sel)
            netn = self._s46_net(R)
            x = np.where(sel, netn, np.nan)
            mean, bs, bt = self._s46_bm(x, rows, two=(nm == "L2"))
            gross = np.where(sel, self._s46_net(R, grossonly=True), np.nan)
            tri = np.where(sel & R["cov"], R["trig"][:, 0], np.nan)
            mt, bts, _ = self._s46_bm(np.where(sel, R["trig"][:, 0], np.nan), rows)
            q1 = sel & tr & (R["etype"][:, 0] == 1); anyp = sel & tr & (R["etype"][:, 0] > 0)
            res[nm] = dict(sel=sel, tr=tr, comp=comp, sh=sh, x=x, mean=mean, bs=bs, bt=bt, gross=gross, trig_bs=bts)
            S(f"D {tag} {nm}", (f"eligible {int(sel.sum())} | minute cov {int((sel & R['cov']).sum())} | breakout30 {int((sel & (R['okb'][:, 0] == 1)).sum())} $1M30 {int((sel & (R['okv'][:, 0] == 1)).sum())} both {int(tr.sum())}"
                                f" ({100 * mt:.1f}% {self._ci(100 * bts, 1)}) | quote entry {int(q1.sum())} any entry {int(anyp.sum())} | complete {int(comp.sum())} same-bar {int((tr & (R['same'][:, 0] == 1)).sum())}")[:198])
            ci2 = f" two-way {self._ci(100 * bt, 2)}" if bt is not None else ""
            cc = R["code"][:, 0]
            S(f"R {tag} {nm}", (f"net neutral mean {100 * mean:+.2f}% {self._ci(100 * bs, 2)}{ci2} median {100 * np.nanmedian(x):+.2f}% | gross {100 * np.nanmean(gross):+.2f}% | win {100 * np.nanmean(x[np.isfinite(x)] > 0):.0f}%"
                                f" | T {sh['target']:.1f} A {sh['adverse']:.1f} amb {sh['ambiguous']:.1f} N {sh['neither']:.1f}% incomplete {int((tr & (cc == 4)).sum())}")[:198])
        if not full:
            return res
        L = res["L2"]; rl = L["sel"]
        # paired comparisons
        cmp_lines = []
        W, W1, W2, du, nsec = self._s46_W()
        for nm in ("STATE", "CTL", "VOLU"):
            o = res[nm]
            d_net = L["bs"] - o["bs"]
            parts = [f"net {100 * (L['mean'] - o['mean']):+.2f}pp {self._ci(100 * d_net, 2)} p {self._pval(d_net):.4f}"]
            tL, tO = L["trig_bs"], o["trig_bs"]
            parts.append(f"trig {100 * (np.nanmean(R['trig'][rl, 0]) - np.nanmean(R['trig'][o['sel'], 0])):+.1f}pp {self._ci(100 * (tL - tO), 1)}")
            for j, lab in ((1, "T"), (3, "A")):
                xa = np.where(L["comp"], (R["code"][:, 0] == j).astype(float), np.nan); xb = np.where(o["comp"], (R["code"][:, 0] == j).astype(float), np.nan)
                ma, ba, _ = self._s46_bm(xa, rows); mb, bb, _ = self._s46_bm(xb, rows)
                parts.append(f"{lab} {100 * (ma - mb):+.1f}pp {self._ci(100 * (ba - bb), 1)}")
            ga, gba, _ = self._s46_bm(L["gross"], rows); gb, gbb, _ = self._s46_bm(o["gross"], rows)
            parts.append(f"gross {100 * (ga - gb):+.2f}pp {self._ci(100 * (gba - gbb), 2)}")
            if nm == "STATE":
                f1, f2 = np.isfinite(L["x"]), np.isfinite(o["x"])
                di1, di2 = np.searchsorted(du, self.D[rows][f1]), np.searchsorted(du, self.D[rows][f2])
                s1, s2 = self.SID[rows][f1], self.SID[rows][f2]
                x1, x2 = L["x"][f1], o["x"][f2]
                bt = np.array([(W1[b][s1] * W2[b][di1] * x1).sum() / max((W1[b][s1] * W2[b][di1]).sum(), 1e-9) - (W1[b][s2] * W2[b][di2] * x2).sum() / max((W1[b][s2] * W2[b][di2]).sum(), 1e-9) for b in range(2000)])
                parts.append(f"two-way net {self._ci(100 * bt, 2)}")
                self.g3 = (L["mean"] - o["mean"] >= 0.01) and (np.percentile(d_net, 2.5) > 0)
            S(f"C {tag} L2-{nm}", " | ".join(parts)[:198])
        # costs and downside (L2 primary)
        cl = []
        for c in ("optimistic", "neutral", "conservative"):
            m, b_, _ = self._s46_bm(np.where(rl, self._s46_net(R, cost=c), np.nan), rows)
            cl.append(f"{c[:4]} {100 * m:+.2f}% {self._ci(100 * b_, 2)}")
        mq, bq, _ = self._s46_bm(np.where(rl, self._s46_net(R, cost="qi"), np.nan), rows)
        cl.append(f"QI {100 * mq:+.2f}% {self._ci(100 * bq, 2)}")
        st = R["strig"][L["tr"], 0]
        S(f"K {tag} L2 costs", (" | ".join(cl) + f" | s_trig p10/25/50/75/90 {q(100 * st[np.isfinite(st)], (10, 25, 50, 75, 90))}%")[:198])
        cp = L["comp"]
        f = lambda a: a[np.isfinite(a)]
        S(f"X {tag} L2 downside", (f"MAE med {100 * np.nanmedian(R['mae'][cp, 0]):.1f}% MFE med {100 * np.nanmedian(R['mfe'][cp, 0]):.1f}% | 5d touch -20/-30/-50 {100 * np.mean(R['minl'][cp, 0] <= -0.2):.0f}/{100 * np.mean(R['minl'][cp, 0] <= -0.3):.0f}/{100 * np.mean(R['minl'][cp, 0] <= -0.5):.0f}%"
                                   f" +20/+30/+50 {100 * np.mean(R['maxh'][cp, 0] >= 0.2):.0f}/{100 * np.mean(R['maxh'][cp, 0] >= 0.3):.0f}/{100 * np.mean(R['maxh'][cp, 0] >= 0.5):.0f}% | close t+1/3/5 med {100 * np.nanmedian(R['c1'][cp, 0]):+.1f}/{100 * np.nanmedian(R['c3'][cp, 0]):+.1f}/{100 * np.nanmedian(R['c5'][cp, 0]):+.1f}%")[:198])
        S(f"X {tag} L2 net pctl", (f"net neutral p5/10/25/50/75/90/95 {q(100 * f(L['x']), (5, 10, 25, 50, 75, 90, 95))}% | hold mean {np.nanmean(R['hold'][cp, 0]):.2f} med {np.nanmedian(R['hold'][cp, 0]):.0f} sessions")[:198])
        for nm in ("STATE", "CTL", "VOLU"):
            cpo = res[nm]["comp"]
            self.lg(f"DOWN {nm}: MAE med {100 * np.nanmedian(R['mae'][cpo, 0]):.1f}% touch -20% {100 * np.mean(R['minl'][cpo, 0] <= -0.2):.0f}% +30% {100 * np.mean(R['maxh'][cpo, 0] >= 0.3):.0f}% close t+5 med {100 * np.nanmedian(R['c5'][cpo, 0]):+.1f}% net p10/50/90 {q(100 * f(res[nm]['x']), (10, 50, 90))}%")
        # selection: triggered vs not
        xr = self.OUT[:, OI["xr"]]
        atr = self.F[:, self.FC45["atr_p"]].astype(np.float64)
        cv = rl & R["cov"]
        parts = []
        for lab, m in (("trig", cv & L["tr"]), ("not", cv & ~L["tr"])):
            ii = rows[m]
            parts.append(f"{lab} n {int(m.sum())} px {np.median(self.RC[ii]):.2f} dv {np.median(self.DVMED[ii]) / 1e6:.2f}M atr {100 * np.nanmedian(atr[ii]):.1f}% xr {100 * np.nanmedian(xr[ii]):.0f}% dv30 {np.nanmedian(R['dv30'][m]) / 1e6:.2f}M")
        S(f"SEL {tag} L2 trig vs not", " | ".join(parts)[:198])
        ti = rows[L["tr"]]
        pe = R["pe"][L["tr"], 0]
        mv = pe / self.PX[ti] - 1; dh = pe / self.RH[ti].astype(np.float64) - 1
        S(f"SEL {tag} L2 entry", (f"entry vs prior close p25/50/75 {q(100 * f(mv), (25, 50, 75))}% | vs prior high {q(100 * f(dh), (25, 50, 75))}% | entry minute after 09:30 p25/50/75 {q(R['emin'][L['tr'], 0] - 570, (25, 50, 75))}")[:198])
        # decomposition vs next open (Stage 4.5 daily bracket)
        ii_all = rows[rl]; ii_tr = rows[L["comp"]]
        no_all = self._s45_payoff(ii_all, COST46["neutral"]); no_tr = self._s45_payoff(ii_tr, COST46["neutral"])
        S(f"DEC {tag} L2", f"next-open all L2 {100 * np.nanmean(no_all):+.2f}% (n {int(np.isfinite(no_all).sum())}) | triggered subset at next open {100 * np.nanmean(no_tr):+.2f}% | triggered at trigger entry {100 * L['mean']:+.2f}% (n {int(np.isfinite(L['x']).sum())})")
        # robustness
        xl = L["x"]
        dts = self.D[rows]
        rb = []
        for lab, (lo, hi) in (("21-22", P21), ("23-25", P23)):
            m = (dts >= lo) & (dts <= hi)
            rb.append(f"{lab} {100 * np.nanmean(np.where(m, xl, np.nan)):+.2f}% n {int((m & np.isfinite(xl)).sum())}")
        yrs = np.array([_date.fromordinal(int(d)).year for d in dts])
        loyo = {y: np.nanmean(np.where(yrs != y, xl, np.nan)) for y in range(2021, 2026)}
        rb.append("LOYO " + " ".join(f"{y % 100}:{100 * v:+.2f}" for y, v in loyo.items()))
        S(f"ROB {tag} periods", " | ".join(rb)[:198])
        sid = self.SID[rows]
        fin = np.isfinite(xl)
        contrib = pd.Series(xl[fin]).groupby(sid[fin]).sum().sort_values(ascending=False)
        top = set(contrib.index[:10])
        m_top = np.nanmean(np.where(~np.isin(sid, list(top)), xl, np.nan))
        hg = np.array([int(hashlib.md5(self.sid_list[s].encode()).hexdigest(), 16) % 10 for s in sid])
        logo = [np.nanmean(np.where(hg != k, xl, np.nan)) for k in range(10)]
        strict = self.U["A-strict"][rows]
        dd = self._s46_dedup(rows, L["comp"] & fin)
        rest = (f"top-10 secs removed {100 * m_top:+.2f}% | sec-group LOO min {100 * min(logo):+.2f} max {100 * max(logo):+.2f} | A-strict {100 * np.nanmean(np.where(strict, xl, np.nan)):+.2f}%"
                f" | dedup5 {100 * np.nanmean(np.where(dd, xl, np.nan)):+.2f}% n {int(dd.sum())} | secs {len(contrib)}")
        S(f"ROB {tag} concentration", rest[:198])
        et = R["etype"][:, 0]
        cons = np.where(rl, self._s46_net(R, mode="conservative"), np.nan)
        gap = np.where(rl, self._s46_net(R, mode="gap"), np.nan)
        qo = np.where(rl & (et == 1), xl, np.nan); po = np.where(rl & (et == 2), xl, np.nan)
        nsb = np.where(rl & (R["same"][:, 0] == 0), xl, np.nan)
        mc, bc, _ = self._s46_bm(cons, rows)
        exa = (f"conservative {100 * mc:+.2f}% {self._ci(100 * bc, 2)} | gap-realistic {100 * np.nanmean(gap):+.2f}% | quote-only {100 * np.nanmean(qo):+.2f}% n {int(np.isfinite(qo).sum())}"
               f" | proxy-only {100 * np.nanmean(po):+.2f}% n {int(np.isfinite(po).sum())} | no same-bar {100 * np.nanmean(nsb):+.2f}%")
        S(f"ROB {tag} execution", exa[:198])
        e1 = (g["lab"][rows] == 1)
        S(f"E1 {tag} diagnostic", f"triggered L2 with E1 move day in t+1..t+3 {int((L['comp'] & e1).sum())}/{int(L['comp'].sum())} | net with move {100 * np.nanmean(np.where(e1, xl, np.nan)):+.2f}% without {100 * np.nanmean(np.where(~e1, xl, np.nan)):+.2f}% (diagnostic only)")
        # gate
        nq = int((L["tr"] & (et == 1)).sum()); ntr = max(int(L["tr"].sum()), 1)
        ncomp = int(np.isfinite(xl).sum())
        lo_s, lo_t = np.percentile(L["bs"], 2.5), np.percentile(L["bt"], 2.5)
        Gs = {"G1": L["mean"] > 0, "G2": lo_s > 0 and lo_t > 0, "G3": bool(getattr(self, "g3", False)),
              "G4": all(v > 0 for v in [np.nanmean(np.where((dts >= lo) & (dts <= hi), xl, np.nan)) for lo, hi in (P21, P23)] + list(loyo.values()) + [m_top] + logo),
              "G5": mc > 0, "G6": (nq / ntr >= 0.8) and np.nanmean(qo) > 0, "G7": True}
        anyent = int((L["tr"] & (et > 0)).sum())
        if ncomp < 300 or anyent / ntr < 0.5:
            dec = "C (inconclusive: data)"
        elif (not Gs["G1"]) or (not Gs["G3"]) or (L["sh"]["adverse"] > L["sh"]["target"] + L["sh"]["neither"]) or (not Gs["G4"]) or (not Gs["G5"]):
            dec = "B (not supported)"
        elif (not Gs["G2"]) or (not Gs["G6"]):
            dec = "C (inconclusive)"
        else:
            dec = "A (controlled execution study)"
        S(f"GATE {tag}", (" ".join(f"{k} {'PASS' if v else 'FAIL'}" for k, v in Gs.items()) + f" | complete {ncomp} quote share {100 * nq / ntr:.0f}% | adverse>target+neither {L['sh']['adverse'] > L['sh']['target'] + L['sh']['neither']} -> {dec}")[:198])
        # secondary sensitivities (after the primary is recorded)
        ps, txt = [], []
        for v in range(1, len(VAR46)):
            xv = np.where(rl, self._s46_net(R, v=v), np.nan)
            m, b_, _ = self._s46_bm(xv, rows)
            p = self._pval(b_) if np.isfinite(m) else 1.0
            ps.append(p)
            txt.append((VAR46[v][0], int((rl & (R["trig"][:, v] == 1)).sum()), int(np.isfinite(xv).sum()), m, self._ci(100 * b_, 2)))
        qv = self._s46_bh(ps)
        S(f"SENS {tag} a", " | ".join(f"{t[0]} trig {t[1]} n {t[2]} {100 * t[3]:+.2f}% {t[4]} q{qq:.2f}" for t, qq in zip(txt[:4], qv[:4]))[:198])
        S(f"SENS {tag} b", " | ".join(f"{t[0]} trig {t[1]} n {t[2]} {100 * t[3]:+.2f}% {t[4]} q{qq:.2f}" for t, qq in zip(txt[4:], qv[4:]))[:198])
        # power for the shadow log
        sd = float(np.nanstd(xl)); nses = max(len(np.unique(dts)), 1)
        nmin = int(np.ceil(((1.645 + 0.842) * sd / 0.02) ** 2))
        rate = ncomp / nses
        S(f"SHADOW {tag} power", f"SD of L2 triggered net payoff {100 * sd:.1f}% -> n_min (delta 2pp, alpha .05 one-sided, power .8) {nmin} | triggered complete L2 per session {rate:.2f} -> about {nmin / max(rate, 1e-9) / 252:.1f} years on the 20% sample")
        # comparison table in the log
        for nm, o in res.items():
            cc = R["code"][:, 0]
            self.lg(f"TABLE {tag} {nm}: eligible {int(o['sel'].sum())} triggered {int(o['tr'].sum())} rate {100 * o['tr'].sum() / max(o['sel'].sum(), 1):.1f}% valid entry {int((o['tr'] & (R['etype'][:, 0] > 0)).sum())}"
                    f" gross {100 * np.nanmean(o['gross']):+.2f}% net {100 * o['mean']:+.2f}% {self._ci(100 * o['bs'], 2)} T {o['sh']['target']:.1f} A {o['sh']['adverse']:.1f} amb {o['sh']['ambiguous']:.1f}"
                    f" incomplete {int((o['tr'] & (cc == 4)).sum())} MAE med {100 * np.nanmedian(R['mae'][o['comp'], 0]):.1f}% P(touch-20) {100 * np.mean(R['minl'][o['comp'], 0] <= -0.2):.0f}%")
        return res

    # ---------------- ROBUST: S2 and 2026 ----------------
    def mode_s46robust(self):
        S = self.set_runtime_statistic
        self._s46_finish()
        out = []
        for tag, un, folds, lo, hi in (("S2 2021-25", "S2", ("a", "b"), T0, T1), ("S1 2026", "S1", ("c",), Y0, Y1)):
            g = self._s46_groups(un, folds, lo, hi, volu=False)
            G = {"L2": g["L2"], "STATE": g["STATE"]}
            rows = np.nonzero(g["L2"] | g["STATE"])[0]
            R = self._s46_run(rows, tlimit_min=120)
            if self.s46_timeout:
                S(f"ERR timeout {tag}", f"stopped at {R['done']}/{len(rows)}")
                continue
            res = self._s46_report(tag, rows, R, G, g, full=False)
            d = res["L2"]["bs"] - res["STATE"]["bs"]
            S(f"C {tag} L2-STATE", f"net {100 * (res['L2']['mean'] - res['STATE']['mean']):+.2f}pp {self._ci(100 * d, 2)} p {self._pval(d):.4f} | rows {len(rows)} loop {R['mins']:.1f} min")
            self._s45_free()
        self._s45_end()

    # ---------------- SHADOW framework ----------------
    def _s46_fingerprint(self, g):
        sc = g["sc"]["L2_FULL"]
        probe = np.nonzero(np.isfinite(sc))[0][::997][:200]
        h1 = hashlib.md5(np.round(sc[probe].astype(np.float64), 8).tobytes()).hexdigest()[:12]
        scT = self._s45_scores()[1]
        pr = np.nonzero(np.isfinite(scT))[0][::997][:200]
        h2 = hashlib.md5(np.round(scT[pr], 8).tobytes()).hexdigest()[:12]
        return h1, h2

    def mode_s46shadow(self):
        S = self.set_runtime_statistic
        self._s46_finish()
        cut = _o(2026, 8, 27)
        g = self._s46_groups("S1", ("c",), Y0, Y1, volu=False)
        f1, f2 = self._s46_fingerprint(g)
        days = np.unique(self.D[self.D > cut])
        os_ok = "n/a"
        try:
            k = "xup_s46_shadow/_selftest"
            if not self.object_store.contains_key(k):
                self.object_store.save(k, json.dumps({"created": str(self.time), "note": "write-once self test"}))
            os_ok = "ok" if self.object_store.contains_key(k) else "write failed"
        except Exception as e:
            os_ok = "error " + type(e).__name__
        S("SH0 shadow status", f"data end {_date.fromordinal(int(self.D.max()))} | prospective sessions after 2026-08-27: {len(days)} | model fingerprints L2 {f1} RF {f2} | ObjectStore {os_ok}")
        # dry run of the logging path on the last 5 historical sessions (labelled DRY RUN, never counted as prospective)
        last = np.unique(self.D[(self.D <= cut)])[-11:-6]
        sel = (g["L2"] | g["STATE"]) & np.isin(self.D, last)
        rows = np.nonzero(sel)[0]
        R = self._s46_run(rows, tlimit_min=20)
        recs = []
        for k_, i in enumerate(rows):
            recs.append({"d": int(self.D[i]), "grp": "L2" if g["L2"][i] else "STATE", "H": float(self.RH[i]), "trig": int(R["trig"][k_, 0]),
                         "m": float(R["emin"][k_, 0]), "pe": float(R["pe"][k_, 0]), "et": int(R["etype"][k_, 0]), "s": float(R["strig"][k_, 0]), "code": int(R["code"][k_, 0]),
                         "net": float(R["gross"][k_, 0] - COST46["neutral"]) if np.isfinite(R["gross"][k_, 0]) else None, "fp": [f1, f2]})
        saved = 0
        try:
            for d in last:
                k = f"xup_s46_shadow_dryrun/{int(d)}"
                if not self.object_store.contains_key(k):
                    self.object_store.save(k, json.dumps([r for r in recs if r["d"] == int(d)]))
                    saved += 1
        except Exception as e:
            saved = -1
        S("SH1 dry run (historical, not prospective)", f"sessions {len(last)} signals {len(rows)} triggered {int(R['trig'][:, 0].sum())} complete-window {int(((R['code'][:, 0] >= 0) & (R['code'][:, 0] <= 3)).sum())} | records written once to ObjectStore {saved} keys")
        self._s45_end()
