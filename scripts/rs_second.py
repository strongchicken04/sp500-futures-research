"""Second RS trade per day (day shift 2026-10-24, fixed before results): after
the first RS funded trade (+/-1.25%) has closed, the next check time (11:00 /
13:00 / 14:30) with an RS signal opens a second trade, same bracket, flat
15:55. Book VG + Z + RS (+ RS2) at 3 MNQ, today's NQ (28,530), open-P&L,
four eras + 2026 holdout book total.
Usage: rs_second.py DATA_DIR
"""
from __future__ import annotations

import statistics as st
import sys

sys.path.insert(0, "scripts")
import funded_model as M  # noqa: E402
import level_lab as L  # noqa: E402
import mtm_check as C  # noqa: E402
from rescore_all import rvol  # noqa: E402
from rs_book import pts as rs_pts  # noqa: E402
from score_multi_feature import parse as parse_mf, LEVELS  # noqa: E402
from score_cond_bracket import parse  # noqa: E402
from size_today import PRICE, rvmap  # noqa: E402

EODM = 955


def rs2(data, suffix, gate, pref):
    sig = lambda r: 1 if (r["rs"] > 0.0015 and r["vwapd"] > 0) else (-1 if (r["rs"] < -0.0015 and r["vwapd"] < 0) else 0)
    ti = si = LEVELS.index(125)
    by = {}
    for r in parse_mf(f"{data}/MFEAT{suffix}_tags.txt"):
        by.setdefault(r["date"], []).append(r)
    out = []
    for d, rows in by.items():
        if not gate(d):
            continue
        rows.sort(key=lambda r: r["hm"])
        first_x, n = None, 0
        for r in rows:
            s = sig(r)
            if not s or (first_x is not None and r["hm"] < first_x):
                continue
            fav, adv = (r["up"], r["dn"]) if s == 1 else (r["dn"], r["up"])
            hits = [k for k in (fav[ti], adv[si]) if k >= 0]
            x = min(EODM, r["hm"] + min(hits)) if hits else EODM
            if n == 1:
                pts = rs_pts(r, s, ti, si)
                c = 1.0 if pts < -0.0124 * r["e"] else 0.75
                pts = (pts + c) / r["e"] * pref - c
                out.append((d, r["hm"], x, pts * 2.0, "RS2", s))
                break
            first_x, n = x, 1
            if x >= EODM:
                break
    return out


def main():
    data = sys.argv[1]
    C.PANEL_LEGS = {}
    reg = rvol()
    ro, r26 = rvmap(data, ("LSVWAP_OLD", "LSNOISE_OLD")), rvmap(data, ("LSVWAP26", "LSNOISE26"))
    eras = (("", ("BARS5A", "BARS5B"), "CBA", lambda d: reg.get(d, 9.0) < 0.30, (("2018", "2022", "2018-21"), ("2022", "2026", "2022-25"))),
            ("_OLD", ("B2_0A", "B2_0B"), "CBA_OLD", lambda d: 0 < ro.get(d, 9.0) < 0.30, (("2010", "2014", "2010-13"), ("2014", "2018", "2014-17"))),
            ("26", ("B2_26",), "CBA26", lambda d: 0 < r26.get(d, 9.0) < 0.30, (("2026", "2027", "2026 H1"),)))
    base_mix, mix2 = {"VG": 3, "Z": 3, "RS": 3}, {"VG": 3, "Z": 3, "RS": 3, "RS2": 3}
    for suf, names, cba, gate, halves in eras:
        L.NAMES = names
        full = sorted({r["date"] for r in parse([f"{data}/{cba}_tags.txt"])})
        tr, by = C.trades(data, suf, gate, PRICE)
        tr = tr + rs2(data, suf, gate, PRICE)
        T = {}
        for t in tr:
            T.setdefault(t[0], []).append(t)
        f = lambda e: PRICE / e
        for lo, hi, lab in halves:
            cal = [d for d in full if lo <= d < hi]
            v = [t[3] for t in tr if t[4] == "RS2" and lo <= t[0] < hi]
            dls = {k: [C.day_seq(T.get(d, []), by[d]["bars"] if d in by else None, m, f, True) for d in cal] for k, m in (("base", base_mix), ("rs2", mix2))}
            if lab == "2026 H1":
                print(f"{lab}: RS2 n {len(v)} ${st.mean(v):+.1f} per MNQ trade | book base ${sum(sum(x) for x in dls['base']):+,.0f} vs + RS2 ${sum(sum(x) for x in dls['rs2']):+,.0f}")
                continue
            paths = M.bootstrap(len(cal), 3000, seed=31)
            c = {k: [M.run_path([dl[i] for i in p], lambda d, s: d) for p in paths] for k, dl in dls.items()}
            print(f"{lab}: RS2 n {len(v)} ${st.mean(v):+.1f} per MNQ trade | book base ${st.mean(c['base']):,.0f}, + RS2 {st.mean(a - b for a, b in zip(c['rs2'], c['base'])):+,.0f}")


if __name__ == "__main__":
    main()
