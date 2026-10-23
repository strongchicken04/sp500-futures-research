"""ICT Silver Bullet (first FVG 10:00-11:00, limit at the gap edge, stop beyond
the gap's first bar, 2R, flat 15:55) as a leg of the no-ORB book, 3 MNQ, vol
gate; costs for a LIMIT entry: $1 round trip (0.5 pt) + 1 tick on stops
(2026-10-23). Paired bootstrap in four eras.
Usage: sb_book.py DATA_DIR
"""
from __future__ import annotations

import sys

sys.path.insert(0, "scripts")
import level_lab as L  # noqa: E402
import ict_lab as I  # noqa: E402
import gate_check as G  # noqa: E402
import old_check as O  # noqa: E402
from mc_book import compare, summary  # noqa: E402
from mc_runs import sized  # noqa: E402
from rescore_all import rvol  # noqa: E402


def leg(data, names, keep):
    L.NAMES = names
    L.COST, L.STOP_COST = 0.5, 0.25
    days = L.load(data)
    return [(t["date"], t["ehm"], t["xhm"], t["pts"] * 2.0, "SB") for t in L.trades(days, lambda d, p: I.sb(d, p, 2.0)) if keep(t["date"])]


def main():
    data = sys.argv[1]
    reg = rvol()
    core = {"VG": 3, "Z": 3, "RS": 3}
    new = leg(data, ("BARS5A", "BARS5B"), lambda d: reg.get(d, 9.0) < 0.30)
    base = [t for t in G.build(data, set()) if t[4] in core]
    allt = O.legs(data)
    gated = {t[0] for t in allt if t[5]}
    onew = leg(data, ("B2_0A", "B2_0B"), lambda d: d in gated)
    obase = [t[:5] for t in allt if t[5] and t[4] in core]
    for tr, halves in ((base + new, (("2018-21", "0", "2022"), ("2022-25", "2022", "9"))), (obase + onew, O.HALVES)):
        cal_all = sorted({t[0] for t in tr})
        for lab, lo, hi in halves:
            cal = [d for d in cal_all if lo <= d < hi]
            v = [t[3] for t in tr if t[4] == "SB" and lo <= t[0] < hi]
            print(f"--- {lab}: SB ${sum(v) / max(1, len(v)):+.2f} per MNQ per trade (n {len(v)})")
            for line in summary(compare({"no ORB (VG+Z+RS)": sized(tr, core), "+ SB 3": sized(tr, dict(core, SB=3)),
                                         "+ SB 1": sized(tr, dict(core, SB=1))}, cal, trials=2500, seed=127), "no ORB (VG+Z+RS)"):
                print("   " + line)


if __name__ == "__main__":
    main()
