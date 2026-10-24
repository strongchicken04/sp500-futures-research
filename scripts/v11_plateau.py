"""Plan-B check (night 2026-10-24/25, fixed before results): the VWAP-side leg
at 11:00 around its parameters at TODAY's NQ (28,530), 3 MNQ, open-P&L
model. Entry at the close of the bar ending 10:55 / 11:00 / 11:05 x bracket
+0.25/-0.40, +0.30/-0.50 (plan B), +0.40/-0.60 %. Added to VG + RS (noise cut)
and to VG + Z + RS; four eras (bootstrap) + 2026 holdout (book total).
Usage: v11_plateau.py DATA_DIR
"""
from __future__ import annotations

import statistics as st
import sys

sys.path.insert(0, "scripts")
import funded_model as M  # noqa: E402
import level_lab as L  # noqa: E402
import mtm_check as C  # noqa: E402
from rescore_all import rvol  # noqa: E402
from score_cond_bracket import parse  # noqa: E402
from size_today import PRICE, rvmap  # noqa: E402
from vside_plateau import vside  # noqa: E402

TIMES = {"10:55": 16, "11:00": 17, "11:05": 18}
BRS = ((0.0025, 0.0040), (0.0030, 0.0050), (0.0040, 0.0060))


def main():
    data = sys.argv[1]
    keys = {f"V{t} {tp * 100:.2f}/{sp * 100:.2f}": vside(i, tp, sp) for t, i in TIMES.items() for tp, sp in BRS}
    C.PANEL_LEGS = keys
    reg = rvol()
    ro, r26 = rvmap(data, ("LSVWAP_OLD", "LSNOISE_OLD")), rvmap(data, ("LSVWAP26", "LSNOISE26"))
    eras = (("", ("BARS5A", "BARS5B"), "CBA", lambda d: reg.get(d, 9.0) < 0.30, (("2018", "2022", "2018-21"), ("2022", "2026", "2022-25"))),
            ("_OLD", ("B2_0A", "B2_0B"), "CBA_OLD", lambda d: 0 < ro.get(d, 9.0) < 0.30, (("2010", "2014", "2010-13"), ("2014", "2018", "2014-17"))),
            ("26", ("B2_26",), "CBA26", lambda d: 0 < r26.get(d, 9.0) < 0.30, (("2026", "2027", "2026 H1"),)))
    res = {}
    labs = []
    for suf, names, cba, gate, halves in eras:
        L.NAMES = names
        full = sorted({r["date"] for r in parse([f"{data}/{cba}_tags.txt"])})
        tr, by = C.trades(data, suf, gate, PRICE)
        T = {}
        for t in tr:
            T.setdefault(t[0], []).append(t)
        f = lambda e: PRICE / e
        for lo, hi, lab in halves:
            labs.append(lab)
            cal = [d for d in full if lo <= d < hi]
            for bname, base_mix in (("VG+RS", {"VG": 3, "RS": 3}), ("VG+Z+RS", {"VG": 3, "Z": 3, "RS": 3})):
                def val(mix):
                    dl = [C.day_seq(T.get(d, []), by[d]["bars"] if d in by else None, mix, f, True) for d in cal]
                    if lab == "2026 H1":
                        return [sum(sum(x) for x in dl)]
                    paths = M.bootstrap(len(cal), 2000, seed=31)
                    return [M.run_path([dl[i] for i in p], lambda d, s: d) for p in paths]
                b = val(base_mix)
                for k in keys:
                    c = val(dict(base_mix, **{k: 3}))
                    res[(bname, k, lab)] = st.mean(x - y for x, y in zip(c, b))
    for bname in ("VG+RS", "VG+Z+RS"):
        print(f"add-on to {bname} at 3 MNQ, NQ {PRICE:,.0f} (cash per seat 24 m; 2026 H1 = book total): " + " / ".join(labs))
        for k in keys:
            v = [res[(bname, k, l)] for l in labs]
            print(f"   {k:<18} " + " / ".join(f"{x:+6,.0f}" for x in v) + ("   ALL +" if min(v) > 0 else ""))


if __name__ == "__main__":
    main()
