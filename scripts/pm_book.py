"""PMTREND (13:00, follow a >= 0.5% morning move, stop 0.5%, flat 15:55) as a
leg of the no-ORB book (VG + Z + RS), 3 MNQ, vol gate; paired bootstrap in all
four eras (2026-10-23).
Usage: pm_book.py DATA_DIR
"""
from __future__ import annotations

import sys

sys.path.insert(0, "scripts")
import level_lab as L  # noqa: E402
import gate_check as G  # noqa: E402
import old_check as O  # noqa: E402
from pm_lab import pm  # noqa: E402
from mc_book import compare, summary  # noqa: E402
from mc_runs import sized  # noqa: E402
from rescore_all import rvol  # noqa: E402


def leg(names, keep):
    L.NAMES = names
    L.COST, L.STOP_COST = 0.75, 0.25
    out = []
    for d in L.load(sys.argv[1]):
        if not keep(d["date"]):
            continue
        r = pm(d["bars"], True)
        if r:
            s, (pts, why, i, k), e = r
            out.append((d["date"], 575 + 5 * i, 575 + 5 * k, pts * 2.0, "PM"))
    return out


def main():
    data = sys.argv[1]
    reg = rvol()
    core = {"VG": 3, "Z": 3, "RS": 3}
    new = leg(("BARS5A", "BARS5B"), lambda d: reg.get(d, 9.0) < 0.30)
    base = [t for t in G.build(data, set()) if t[4] in core]
    allt = O.legs(data)
    gated = {t[0] for t in allt if t[5]}
    onew = leg(("B2_0A", "B2_0B"), lambda d: d in gated)
    obase = [t[:5] for t in allt if t[5] and t[4] in core]
    for tr, halves in ((base + new, (("2018-21", "0", "2022"), ("2022-25", "2022", "9"))), (obase + onew, O.HALVES)):
        cal_all = sorted({t[0] for t in tr})
        for lab, lo, hi in halves:
            cal = [d for d in cal_all if lo <= d < hi]
            v = [t[3] for t in tr if t[4] == "PM" and lo <= t[0] < hi]
            print(f"--- {lab}: PM ${sum(v) / max(1, len(v)):+.2f} per MNQ per trade (n {len(v)})")
            for line in summary(compare({"no ORB (VG+Z+RS)": sized(tr, core), "+ PM 3": sized(tr, dict(core, PM=3))}, cal, trials=2500, seed=101), "no ORB (VG+Z+RS)"):
                print("   " + line)


if __name__ == "__main__":
    main()
