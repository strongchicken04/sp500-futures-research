"""Leg importance with the paired bootstrap: the candidate book (VG + Z without
gate + RS + OD, flat 3) with each leg removed in turn, and each leg's size 2 / 4.
Usage: mc_legs.py DATA_DIR
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
    zfree = G.build(data, {"Z"})
    reg = rvol()
    od = [(t["date"], t["ehm"], t["xhm"], t["pts"] * 2.0, "OD") for t in L.trades(L.load(data), lambda d, p: L.odrive(d, p, 0.0005, 0.0015))
          if reg.get(t["date"], 9.0) < 0.30]
    tr = zfree + od
    cand = {"VG": 3, "Z": 3, "RS": 3, "OD": 3}
    cal_all = sorted({t[0] for t in tr})
    for lo, hi in (("0", "2022"), ("2022", "9")):
        cal = [d for d in cal_all if lo <= d < hi]
        V = {"candidate VG3 Z3 RS3 OD3": sized(tr, cand)}
        for leg in cand:
            V[f"without {leg}"] = sized(tr, {k: v for k, v in cand.items() if k != leg})
        for leg in cand:
            for n in (2, 4):
                V[f"{leg} at {n}"] = sized(tr, dict(cand, **{leg: n}))
        print(f"--- {'2018-2021' if lo == '0' else '2022-2025'}")
        for line in summary(compare(V, cal, trials=3000, seed=31), "candidate VG3 Z3 RS3 OD3"):
            print("   " + line)


if __name__ == "__main__":
    main()
