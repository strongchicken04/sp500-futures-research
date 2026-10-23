"""Combined candidate books vs the current book, paired block bootstrap
(mc_book.py). Candidates built from today's single changes that were positive
in BOTH halves: drop ORB, noise without the vol gate, add open drive (OD).
Usage: mc_combo.py DATA_DIR
"""
from __future__ import annotations

import sys

sys.path.insert(0, "scripts")
import level_lab as L  # noqa: E402
import gate_check as G  # noqa: E402
from mc_book import compare, summary  # noqa: E402
from mc_runs import sized  # noqa: E402
from rescore_all import rvol  # noqa: E402


def main():
    data = sys.argv[1]
    base = G.build(data, set())
    zfree = G.build(data, {"Z"})
    days = L.load(data)
    reg = rvol()
    od = [(t["date"], t["ehm"], t["xhm"], t["pts"] * 2.0, "OD") for t in L.trades(days, lambda d, p: L.odrive(d, p, 0.0005, 0.0015))
          if reg.get(t["date"], 9.0) < 0.30]
    four = {"ORB": 3, "VG": 3, "Z": 3, "RS": 3}
    cal_all = sorted({t[0] for t in base + zfree + od})
    for lo, hi in (("0", "2022"), ("2022", "9")):
        cal = [d for d in cal_all if lo <= d < hi]
        V = {
            "now: ORB+VG+Z+RS flat 3": sized(base, four),
            "VG+Z+RS (no ORB)": sized(base, {"VG": 3, "Z": 3, "RS": 3}),
            "VG+Zfree+RS": sized(zfree, {"VG": 3, "Z": 3, "RS": 3}),
            "VG+Zfree+RS+OD": sized(zfree + od, {"VG": 3, "Z": 3, "RS": 3, "OD": 3}),
            "VG+Z+RS+OD": sized(base + od, {"VG": 3, "Z": 3, "RS": 3, "OD": 3}),
            "VG+Zfree+RS+OD flat 4": sized(zfree + od, {"VG": 4, "Z": 4, "RS": 4, "OD": 4}),
            "ORB+VG+Z+RS flat 4": sized(base, {k: 4 for k in four}),
        }
        print(f"--- {'2018-2021' if lo == '0' else '2022-2025'} ({len(cal)} days), mean 24-month cash per account")
        for line in summary(compare(V, cal, trials=4000, seed=23), "now: ORB+VG+Z+RS flat 3"):
            print("   " + line)


if __name__ == "__main__":
    main()
