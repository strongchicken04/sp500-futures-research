# region imports
from AlgorithmImports import *
from datetime import date as _date
import numpy as np
import pandas as pd
from xup_s3_const import *
from xup_s3_modes_m import SPECS, _split
# endregion
#
# Stage 4 core (research/extreme_upside/stage4/protocol.md). Attached to the Stage 3 panel class by run_s4.sh.
# Adds, WITHOUT changing any Stage 3 array: segment ids, forward-path outcomes and path-excursion flags (wrapper
# around _security), refits of the frozen Stage 3 specifications, Stage 4 daily ranking, event construction
# (E1 / E2 / E3), signal-event association, deduplication and bootstrap helpers. Aggregates only leave QC.

OC = ["mh10", "mc10", "c5", "c10", "c20", "ml10", "ml20", "mh20", "mc20", "tmax10", "t50", "t100", "t200", "tc100", "advpre", "xr"]
OI = {k: i for i, k in enumerate(OC)}
_o = lambda y, m, d: _date(y, m, d).toordinal()
SCORE_START = _o(2020, 11, 2)
T0, T1 = _o(2021, 1, 1), _o(2025, 12, 31)
Y0, Y1 = _o(2026, 1, 1), DATA_END.toordinal()
V0, V1, VSCORE = _o(2017, 1, 1), _o(2020, 12, 31), _o(2016, 11, 1)
MN = ["fullA RF", "volume LR", "price LR", "momentum LR", "fullA LR", "fullA GBM"]
SHORT = {"fullA RF": "RF", "volume LR": "VOL", "price LR": "PRICE", "momentum LR": "MOM", "fullA LR": "LR", "fullA GBM": "GBM"}
PX_EDGES = [0.10, 0.50, 1.0, 3.0, 5.0, 10.0]
PX_LAB = ["<0.10", "0.10-0.49", "0.50-0.99", "1-2.99", "3-4.99", "5-9.99", ">=10"]
DV_EDGES = [1e5, 5e5, 1e6, 5e6, 1e7]
DV_LAB = ["<100k", "100-500k", "500k-1M", "1-5M", "5-10M", ">10M"]


def q(a, ps=(10, 25, 50, 75, 90)):
    a = np.asarray(a, dtype=np.float64)
    a = a[np.isfinite(a)]
    if len(a) == 0:
        return "/".join("na" for _ in ps)
    return "/".join(f"{v:.3g}" for v in np.percentile(a, ps))


def pct(a, b):
    return f"{100.0 * a / b:.1f}%" if b else "na"


class S4Core:

    # ---------------- panel extension (wrapper around the Stage 3 _security) ----------------
    def _security(self, sid, cls, adj, raw):
        r = self._security_s3(sid, cls, adj, raw)
        if r is None:
            return None
        if not hasattr(self, "X4"):
            self.X4 = []
        n = len(r[0])
        try:
            ex = self._s4_extras(adj, raw, r[0])
        except Exception as e:
            self.err.append("s4x " + str(e)[:60])
            ex = (np.full(n, -1, np.int32), np.full(n, -1, np.int32), np.full((n, len(OC)), np.nan, np.float32))
        self.X4.append(ex)
        return r

    def _s4_extras(self, adj, raw, keep_dates):
        ds, o, hi, lo, c, v = adj
        rds = raw[0]
        if len(ds) != len(rds) or not np.array_equal(ds, rds):
            m = {d: i for i, d in enumerate(rds)}
            ok = np.array([d in m for d in ds])
            ds, o, hi, lo, c = ds[ok], o[ok], hi[ok], lo[ok], c[ok]
        md = np.array([self.mdi.get(int(d), -1) for d in ds])
        okm = md >= 0
        ds, o, hi, lo, c, md = ds[okm], o[okm], hi[okm], lo[okm], c[okm], md[okm]
        n = len(ds)
        seg = np.concatenate([[0], np.cumsum(np.diff(md) > 11)]).astype(np.int32)
        X = np.full((n, len(OC)), np.nan, dtype=np.float32)
        endm = self.mdi[DATA_END.toordinal()] if DATA_END.toordinal() in self.mdi else 10 ** 9
        sw = np.lib.stride_tricks.sliding_window_view
        for sg in np.unique(seg):
            ii = np.nonzero(seg == sg)[0]
            a, b = ii[0], ii[-1] + 1
            ns = b - a
            oo, hh, ll, cc, MD = o[a:b], hi[a:b], lo[a:b], c[a:b], md[a:b]
            # path excursion ratio at day tau: HIGH(tau) / min OPEN(tau-9 .. tau) - 1 (needs 10 sessions)
            if ns >= 10:
                mo = pd.Series(oo).rolling(10, min_periods=10).min().values
                with np.errstate(divide="ignore", invalid="ignore"):
                    X[a:b, OI["xr"]] = np.where(mo > 0, hh / mo - 1, np.nan)
            for h in (5, 10, 20):
                m = ns - h
                if m <= 0:
                    continue
                ref = oo[1:m + 1]
                okr = (ref > 0) & (MD[h:h + m] <= endm)
                Wh = sw(hh[1:], h)[:m]; Wc = sw(cc[1:], h)[:m]; Wl = sw(ll[1:], h)[:m]
                with np.errstate(divide="ignore", invalid="ignore"):
                    rr = ref[:, None]
                    mh = Wh.max(axis=1) / ref - 1
                    mc = Wc.max(axis=1) / ref - 1
                    ml = Wl.min(axis=1) / ref - 1
                    ec = cc[h:h + m] / ref - 1
                    if h == 5:
                        X[a:a + m, OI["c5"]] = np.where(okr, ec, np.nan)
                        continue
                    if h == 20:
                        X[a:a + m, OI["c20"]] = np.where(okr, ec, np.nan)
                        X[a:a + m, OI["ml20"]] = np.where(okr, ml, np.nan)
                        X[a:a + m, OI["mh20"]] = np.where(okr, mh, np.nan)
                        X[a:a + m, OI["mc20"]] = np.where(okr, mc, np.nan)
                        continue
                    X[a:a + m, OI["mh10"]] = np.where(okr, mh, np.nan)
                    X[a:a + m, OI["mc10"]] = np.where(okr, mc, np.nan)
                    X[a:a + m, OI["c10"]] = np.where(okr, ec, np.nan)
                    X[a:a + m, OI["ml10"]] = np.where(okr, ml, np.nan)
                    X[a:a + m, OI["tmax10"]] = np.where(okr, Wh.argmax(axis=1) + 1, np.nan)
                    for thr, nm in ((0.5, "t50"), (1.0, "t100"), (2.0, "t200")):
                        hit = Wh >= (1 + thr) * rr
                        X[a:a + m, OI[nm]] = np.where(okr, np.where(hit.any(axis=1), hit.argmax(axis=1) + 1, 0), np.nan)
                    hitc = Wc >= 2 * rr
                    X[a:a + m, OI["tc100"]] = np.where(okr, np.where(hitc.any(axis=1), hitc.argmax(axis=1) + 1, 0), np.nan)
                    t1 = np.where(Wh >= 2 * rr, 1, 0)
                    first = np.where(t1.any(axis=1), t1.argmax(axis=1) + 1, 0)
                    lowm = np.where(np.arange(h)[None, :] < first[:, None], Wl, np.inf).min(axis=1)
                    X[a:a + m, OI["advpre"]] = np.where(okr & (first > 0), lowm / ref - 1, np.nan)
        idx = np.searchsorted(ds, keep_dates)
        if np.any(idx >= n) or not np.array_equal(ds[np.minimum(idx, n - 1)], keep_dates):
            raise ValueError("s4 date alignment")
        return md[idx].astype(np.int32), seg[idx], X[idx]

    def _s4_finish(self):
        """concatenate the Stage 4 extension, verify it against the Stage 3 panel; returns check text"""
        if getattr(self, "s4_ready", False):
            return self.s4_check
        X4 = self.X4
        assert len(X4) == len(self.sid_list), "X4 / parts misaligned"
        self.MDX = np.concatenate([x[0] for x in X4])
        segl = np.concatenate([x[1] for x in X4]).astype(np.int64)
        self.OUT = np.concatenate([x[2] for x in X4])
        assert len(self.OUT) == len(self.D), "X4 length"
        self.X4 = None
        self.GS = self.SID.astype(np.int64) * 100000 + segl
        n = len(self.D)
        chg = np.ones(n, dtype=bool)
        chg[1:] = self.GS[1:] != self.GS[:-1]
        starts = np.nonzero(chg)[0]
        ends = np.append(starts[1:], n) - 1
        k = np.cumsum(chg) - 1
        self.SEG0 = starts[k]
        self.SEG1 = ends[k]
        self.PX = np.exp(self.F[:, FI["lpx"]]).astype(np.float64)
        self.DV = np.expm1(self.F[:, FI["ldv"]]).astype(np.float64)
        a, b = self.OUT[:, OI["mh10"]], self.R
        nanmis = int((np.isnan(a) != np.isnan(b)).sum())
        fin = np.isfinite(a) & np.isfinite(b)
        valmis = int((np.abs(a[fin] - b[fin]) > 1e-6 * np.maximum(1, np.abs(b[fin]))).sum())
        dup = int((~chg[1:] & (self.D[1:] <= self.D[:-1])).sum())
        prim = self.L[:, PRIMARY]
        self.s4_check = (f"rows {n} (S3 6022604) primary events {int((prim == 1).sum())} (S3 24371) | mh10 vs R mismatches: nan {nanmis} value {valmis}"
                         f" | non-increasing dates within segment {dup} | segments {len(starts)} | s4 extension errors {sum(1 for e in self.err if e.startswith('s4x'))}")
        self.s4_ok = (n == 6022604 and int((prim == 1).sum()) == 24371 and nanmis == 0 and valmis == 0 and dup == 0)
        self.s4_ready = True
        self.set_runtime_statistic("S4 CHECK", ("OK " if self.s4_ok else "FAILED ") + self.s4_check[:185])
        return self.s4_check

    # ---------------- frozen models ----------------
    def _s4_fit(self, name, test=True, cache=True):
        if not hasattr(self, "_fc"):
            self._fc = {}
        if cache and (name, test) in self._fc:
            return self._fc[(name, test)]
        spec = [s for s in SPECS if s[0] == name][0]
        _, uni, feats, kind, sp = spec
        tr, _, _ = _split(self, sp, test)
        idx, y, w = self._train_rows(self.U[uni] & tr, PRIMARY)
        cols = [FI[c] for c in feats]
        f, _m = self._fit(kind, self.F[idx][:, cols], y, w)
        if cache:
            self._fc[(name, test)] = (f, cols)
        return f, cols

    def _s4_score(self, names, test=True, lo=None, hi=None):
        """refit frozen specs (TEST split if test else MODEL split) and score universe-A rows in [lo, hi]"""
        lo = SCORE_START if lo is None else lo
        hi = Y1 if hi is None else hi
        mask = self.U["A"] & (self.D >= lo) & (self.D <= hi)
        rows = np.nonzero(mask)[0]
        out = {}
        for nm in names:
            f, cols = self._s4_fit(nm, test)
            s = np.empty(len(rows), dtype=np.float64)
            for a in range(0, len(rows), 400000):
                r = rows[a:a + 400000]
                s[a:a + 400000] = f(self.F[r][:, cols])
            full = np.full(len(self.D), np.nan)
            full[rows] = s
            out[nm] = full
        return out

    def _s4_flags(self, s, mask, ks=(0.01, 0.05, 0.10)):
        """Stage 4 daily ranking inside mask (all eligible rows, label validity ignored); returns {k: bool array}, pct rank"""
        rows = np.nonzero(mask & np.isfinite(s))[0]
        pr = np.full(len(self.D), np.nan)
        pr[rows] = self._dayrank(s[rows], self.D[rows])
        return {k: np.nan_to_num(pr, nan=9.0) <= k for k in ks}, pr

    # ---------------- events ----------------
    def _s4_events(self, li, rule, mask=None, h=10):
        """E1 (Stage 3 _episodes), E2 (merged forward windows), E3 (price-path excursions). Returns dict of arrays."""
        n = len(self.D)
        m = np.ones(n, dtype=bool) if mask is None else mask
        if rule == "E3":
            pos = m & (self.OUT[:, OI["xr"]] >= 1.0)
            val = self.OUT[:, OI["xr"]]
        else:
            pos = m & (self.L[:, li] == 1)
            val = self.R
        idx = np.nonzero(pos)[0]
        st, la, npos, mx = [], [], [], []
        last_key, ref_i, W = None, -10 ** 9, -10 ** 9
        for i in idx:
            if rule == "E1":
                key = self.SID[i]
                new = key != last_key or i - ref_i >= h
            elif rule == "E2":
                key = self.GS[i]
                new = key != last_key or i > W
            else:
                key = self.GS[i]
                new = key != last_key or i - ref_i > h
            v = val[i]
            if new:
                st.append(i); la.append(i); npos.append(1); mx.append(v if np.isfinite(v) else -1)
                last_key = key
                ref_i = i
                W = i + h
            else:
                la[-1] = i; npos[-1] += 1
                if np.isfinite(v) and v > mx[-1]:
                    mx[-1] = v
                W = max(W, i + h)
                if rule == "E3":
                    ref_i = i
        ev = dict(start=np.array(st, dtype=np.int64), last=np.array(la, dtype=np.int64), npos=np.array(npos), mx=np.array(mx, dtype=np.float64))
        s, l = ev["start"], ev["last"]
        ev["sid"] = self.SID[s]
        ev["date"] = self.D[s]
        ev["year"] = self.Y[s]
        ev["px"] = self.PX[s]
        ev["dv"] = self.DV[s]
        cB = np.concatenate([[0], np.cumsum(self.L[:, TI[("B", 10, 1.0)]] == 1)])
        cM = np.concatenate([[0], np.cumsum(self.L[:, TI[("M", 10, 1.0)]] == 1)])
        ev["confB"] = (cB[l + 1] - cB[s]) > 0
        ev["confM"] = (cM[l + 1] - cM[s]) > 0
        lab = self.L[:, li] if rule != "E3" else self.L[:, PRIMARY]
        cI = np.concatenate([[0], np.cumsum(lab == -1)])
        hi = np.minimum(l + h, self.SEG1[l])
        ev["incomplete"] = ((cI[hi + 1] - cI[l + 1]) > 0) | (self.SEG1[l] < l + h)
        ev["adv"] = self.OUT[s, OI["advpre"]].astype(np.float64)
        return ev

    def _s4_assoc(self, ev, h=10):
        """row -> associated event id (pre-onset window, then in-event range overwrites), and in-event flag"""
        n = len(self.D)
        aid = np.full(n, -1, dtype=np.int64)
        ain = np.zeros(n, dtype=bool)
        lo = np.maximum(ev["start"] - h, self.SEG0[ev["start"]])
        for e in range(len(ev["start"])):
            aid[lo[e]:ev["start"][e]] = e
        for e in range(len(ev["start"])):
            aid[ev["start"][e]:ev["last"][e] + 1] = e
            ain[ev["start"][e]:ev["last"][e] + 1] = True
        return aid, ain

    def _wcount(self, cf, a, b):
        """number of flags in rows [a, b] from cumulative cf (cf[i+1] = flags in rows <= i); empty if b < a"""
        return np.where(b >= a, cf[np.maximum(b, a - 1) + 1] - cf[a], 0)

    def _s4_capture(self, ev, sel, flag, h=10, pw=(31, 40)):
        """per selected event: pre (onset-h..onset-1), during (onset..last), placebo (onset-40..onset-31) counts,
        first-signal lead within 40 sessions; windows truncated by segment / scoring start are flagged"""
        cf = np.concatenate([[0], np.cumsum(flag)])
        s, l = ev["start"][sel], ev["last"][sel]
        s0 = self.SEG0[s]
        lo = np.maximum(s - h, s0)
        pre = self._wcount(cf, lo, s - 1)
        dur = self._wcount(cf, s, l)
        plo, phi = s - pw[1], s - pw[0]
        pok = (plo >= s0)
        pok &= self.D[np.maximum(plo, 0)] >= SCORE_START
        plac = np.where(pok, self._wcount(cf, np.maximum(plo, s0), np.maximum(phi, s0)), 0)
        fi = np.nonzero(flag)[0]
        lo40 = np.maximum(s - 40, s0)
        j = np.searchsorted(fi, lo40)
        jj = np.minimum(j, max(len(fi) - 1, 0))
        has = (j < len(fi)) & (fi[jj] < s) if len(fi) else np.zeros(len(s), dtype=bool)
        lead = np.where(has, s - fi[jj], 0)
        return dict(pre=pre, dur=dur, plac=plac, pok=pok, lead=lead, sid=ev["sid"][sel])

    def _s4_dedup(self, flag, rule, aid=None, rows=None):
        """deployable rules N0 / C10 / C20 / CW and the retrospective CE; flags considered only in rows (bool mask)"""
        fi = np.nonzero(flag & (rows if rows is not None else True))[0]
        keep = np.zeros(len(self.D), dtype=bool)
        if rule == "N0":
            keep[fi] = True
            return keep
        gap = {"C10": 10, "C20": 20, "CW": 10, "CE": 10}[rule]
        lk_g, lk_i, la_g, la_i = -1, -10 ** 9, -1, -10 ** 9
        seen = set()
        G = self.GS
        for i in fi:
            g = G[i]
            if rule == "CW":
                ok = (g != la_g) or (i - la_i > gap)
                la_g, la_i = g, i
            elif rule == "CE" and aid is not None and aid[i] >= 0:
                ok = aid[i] not in seen
                seen.add(aid[i])
                if ok:
                    keep[i] = True
                continue
            else:
                ok = (g != lk_g) or (i - lk_i > gap)
            if ok:
                keep[i] = True
                lk_g, lk_i = g, i
        return keep

    # ---------------- bootstrap helpers ----------------
    def _boot_W(self, B, seed, n):
        return np.random.RandomState(seed).poisson(1.0, size=(B, n)).astype(np.float32)

    def _ap_sorted(self, ys, w):
        wy = w * ys
        tp = np.cumsum(wy)
        cnt = np.cumsum(w)
        return float((wy * tp / np.maximum(cnt, 1e-9)).sum() / max(wy.sum(), 1e-9))

    def _ci(self, a, d=4):
        a = np.asarray(a)
        return f"[{np.percentile(a, 2.5):.{d}f},{np.percentile(a, 97.5):.{d}f}]"

    def _pval(self, a):
        a = np.asarray(a)
        return min(1.0, max(2 * min((a <= 0).mean(), (a >= 0).mean()), 1.0 / len(a)))

    def _strata_px(self, px):
        return np.searchsorted(np.array(PX_EDGES), px, side="right")

    def _strata_dv(self, dv):
        return np.searchsorted(np.array(DV_EDGES), dv, side="right")
