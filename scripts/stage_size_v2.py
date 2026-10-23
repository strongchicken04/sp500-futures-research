"""Size by account stage on the corrected model with the open-P&L check
(night shift 2026-10-23/24, fixed before results). Book VG + Z + RS, n MNQ per
leg before the first payout -> m after it (the account then has >= $1,900
cushion plus any profit kept above +$4,000):
  4->4 (flat 4, base) | 3->4 | 3->5 | 4->5 | 4->3 | 5->4
Four eras, 2010-17 re-priced at today's NQ.
Usage: stage_size_v2.py DATA_DIR
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

PAIRS = ((4, 4), (3, 4), (3, 5), (4, 5), (4, 3), (5, 4))


def main():
    data = sys.argv[1]
    reg = rvol()
    pref = st.mean(float(p.split(",")[5]) for p in open(f"{data}/LSNOISE_tags.txt")
                   if p.startswith(("L,NS,2022", "L,NS,2023", "L,NS,2024", "L,NS,2025")))
    rvo = {}
    for f in ("LSVWAP_OLD", "LSNOISE_OLD"):
        for raw in open(f"{data}/{f}_tags.txt"):
            p = raw.strip().split(",")
            if p[0] == "L" and len(p) >= 10 and int(p[9]) > 0:
                rvo[f"{p[2][:4]}-{p[2][4:6]}-{p[2][6:]}"] = int(p[9]) / 1000.0
    eras = (("", ("BARS5A", "BARS5B"), "CBA", lambda d: reg.get(d, 9.0) < 0.30, None,
             (("2018", "2022", "2018-21"), ("2022", "2026", "2022-25"))),
            ("_OLD", ("B2_0A", "B2_0B"), "CBA_OLD", lambda d: 0 < rvo.get(d, 9.0) < 0.30, pref,
             (("2010", "2014", "2010-13"), ("2014", "2018", "2014-17"))))
    for suf, names, cba, gate, pr, halves in eras:
        L.NAMES = names
        full = sorted({r["date"] for r in parse([f"{data}/{cba}_tags.txt"])})
        tr, by = C.trades(data, suf, gate, pr)
        T = {}
        for t in tr:
            T.setdefault(t[0], []).append(t)
        f = (lambda e: pref / e) if pr else None
        for lo, hi, lab in halves:
            cal = [d for d in full if lo <= d < hi]
            DL = {n: [C.day_seq(T.get(d, []), by[d]["bars"] if d in by else None, {"VG": n, "Z": n, "RS": n}, f, True) for d in cal]
                  for n in (3, 4, 5)}
            days = list(range(len(cal)))
            paths = M.bootstrap(len(cal), 3000, seed=31)
            base = None
            cells = []
            for a, b in PAIRS:
                fn = lambda i, s, a=a, b=b: DL[a if s["pays"] == 0 else b][i]
                cash = [M.run_path([days[i] for i in p], fn) for p in paths]
                base = base or cash
                d = [x - y for x, y in zip(cash, base)]
                cells.append(f"{a}->{b} ${st.mean(cash):7,.0f} ({st.mean(d):+6,.0f})")
            print(f"{lab}: " + " | ".join(cells))


if __name__ == "__main__":
    main()
