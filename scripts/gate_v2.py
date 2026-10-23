"""Vol gate (prior-day 20d realised vol < 0.30) per leg on the open-P&L model
at 4 MNQ (night shift 2026-10-23/24, fixed before results): all gated (today)
vs Z ungated, VG ungated, RS ungated, all ungated. Four eras (2010-17
re-priced at today's NQ). Days without a gate value count as gated-out as
before (live-spec rv field / rvol()).
Usage: gate_v2.py DATA_DIR
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

MIX = {"VG": 4, "Z": 4, "RS": 4}
VAR = {"all gated": set(), "Z ungated": {"Z"}, "VG ungated": {"VG"}, "RS ungated": {"RS"}, "none gated": {"VG", "Z", "RS"}}


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
    res = {}
    for suf, names, cba, gate, pr, halves in eras:
        L.NAMES = names
        full = sorted({r["date"] for r in parse([f"{data}/{cba}_tags.txt"])})
        f = (lambda e: pref / e) if pr else None
        for name, ung in VAR.items():
            C.UNGATED = ung
            tr, by = C.trades(data, suf, gate, pr)
            T = {}
            for t in tr:
                T.setdefault(t[0], []).append(t)
            for lo, hi, lab in halves:
                cal = [d for d in full if lo <= d < hi]
                paths = M.bootstrap(len(cal), 3000, seed=31)
                dl = [C.day_seq(T.get(d, []), by[d]["bars"] if d in by else None, MIX, f, True) for d in cal]
                res[(lab, name)] = [M.run_path([dl[i] for i in p], lambda d, s: d) for p in paths]
    C.UNGATED = set()
    for lab in ("2018-21", "2022-25", "2010-13", "2014-17"):
        b = res[(lab, "all gated")]
        print(f"{lab}: " + " | ".join(f"{n}: ${st.mean(res[(lab, n)]):7,.0f} ({st.mean(x - y for x, y in zip(res[(lab, n)], b)):+6,.0f})" for n in VAR))


if __name__ == "__main__":
    main()
