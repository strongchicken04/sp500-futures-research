"""Small-edge funded legs re-tested on the corrected account model with the
open-P&L check (day shift 2026-10-24, fixed before results). All were
rejected on the old model ("more busts than profit"); the corrected model
keeps the profit above a payout and favours more risk where the edge is real.
Base: VG + Z + RS at 4 MNQ. Add one leg at 4 MNQ (vol gate as the others):
  OD    open drive (10:00, Lucid 10)
  NR    NR4 break (first 5-min close outside 09:30-10:00 after an NR4 day)
  PM    PMTREND (13:00, follow a >= 0.5% morning, stop 0.5%)
  SB    ICT Silver Bullet 2R (first FVG 10-11, limit entry)
  T14   14:00 trend (above VWAP and the initial balance high, stop at VWAP)
  V10   VWAP side at 10:00, +0.30% / -0.50%
Four eras (2010-17 re-priced at today's NQ). A leg is adopted only if it adds
in all four eras.
Usage: addons_mtm.py DATA_DIR
"""
from __future__ import annotations

import statistics as st
import sys

sys.path.insert(0, "scripts")
import funded_model as M  # noqa: E402
import level_lab as L  # noqa: E402
import ict_lab as I  # noqa: E402
import mtm_check as C  # noqa: E402
from mc_simple import nr4  # noqa: E402
from pm_lab import pm  # noqa: E402
from rescore_all import rvol  # noqa: E402
from score_cond_bracket import parse  # noqa: E402


def pm_fn(days):
    def f(d, p):
        r = pm(d["bars"], True)
        return (r[0], r[1]) if r else None
    return f


def v10_fn(days):
    def f(d, p):
        b = d["bars"]
        c, vw = b[5][3], L.vwaps(b)[5]
        s = 1 if c > vw else -1 if c < vw else 0
        return (s, L.run(b, 5, s, c, c * (1 - s * 0.005), c * (1 + s * 0.003))) if s else None
    return f


C.PANEL_LEGS = {"OD": lambda days: (lambda d, p: L.odrive(d, p, 0.0005, 0.0015)), "NR": nr4, "PM": pm_fn,
                "SB": lambda days: (lambda d, p: I.sb(d, p, 2.0)), "T14": lambda days: L.trend14, "V10": v10_fn}
BASE = {"VG": 4, "Z": 4, "RS": 4}


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
    variants = {"base": BASE, **{f"+ {k}": dict(BASE, **{k: 4}) for k in C.PANEL_LEGS}}
    for suf, names, cba, gate, pr, halves in eras:
        L.NAMES = names
        L.COST, L.STOP_COST = 0.75, 0.25
        full = sorted({r["date"] for r in parse([f"{data}/{cba}_tags.txt"])})
        tr, by = C.trades(data, suf, gate, pr)
        T = {}
        for t in tr:
            T.setdefault(t[0], []).append(t)
        f = (lambda e: pref / e) if pr else None
        for leg in C.PANEL_LEGS:
            v = [t[3] for t in tr if t[4] == leg]
            print(f"   {leg:<4} {names[0][:-1]}: n {len(v)}, ${st.mean(v):+.2f} per MNQ trade")
        for lo, hi, lab in halves:
            cal = [d for d in full if lo <= d < hi]
            paths = M.bootstrap(len(cal), 3000, seed=31)
            base = None
            cells = []
            for name, mix in variants.items():
                dl = [C.day_seq(T.get(d, []), by[d]["bars"] if d in by else None, mix, f, True) for d in cal]
                cash = [M.run_path([dl[i] for i in p], lambda d, s: d) for p in paths]
                fp = [r for r in (M.first_payout(dl[s:], lambda d, s: d) for s in range(len(dl) - 250)) if r]
                base = base or cash
                dd = [a - b for a, b in zip(cash, base)]
                cells.append(f"{name} {st.mean(dd):+6,.0f} ({sum(r for r, _ in fp) / len(fp) * 100:4.1f}%)")
            print(f"{lab}: base ${st.mean(base):7,.0f} | " + " | ".join(cells[1:]) + f" | base first payout {cells[0].split('(')[1]}")


if __name__ == "__main__":
    main()
