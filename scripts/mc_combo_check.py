"""Adversarial re-check of the combo result (mc_combo.py): block length 5 / 60
days, and the original time-aware walk (timed_book outcomes + life) on one
common calendar.
Usage: mc_combo_check.py DATA_DIR
"""
from __future__ import annotations

import sys

sys.path.insert(0, "scripts")
import level_lab as L  # noqa: E402
import gate_check as G  # noqa: E402
import mc_book as M  # noqa: E402
from mc_runs import sized  # noqa: E402
from rescore_all import rvol  # noqa: E402
from timed_book import days_for, outcomes, life  # noqa: E402


def main():
    data = sys.argv[1]
    base = G.build(data, set())
    zfree = G.build(data, {"Z"})
    reg = rvol()
    od = [(t["date"], t["ehm"], t["xhm"], t["pts"] * 2.0, "OD") for t in L.trades(L.load(data), lambda d, p: L.odrive(d, p, 0.0005, 0.0015))
          if reg.get(t["date"], 9.0) < 0.30]
    four = {"ORB": 3, "VG": 3, "Z": 3, "RS": 3}
    V = {"now": sized(base, four), "VG+Zfree+RS": sized(zfree, {"VG": 3, "Z": 3, "RS": 3}),
         "VG+Zfree+RS+OD": sized(zfree + od, {"VG": 3, "Z": 3, "RS": 3, "OD": 3})}
    cal_all = sorted({t[0] for t in base + zfree + od})
    for blk in (5, 60):
        M.BLOCK = blk
        for lo, hi in (("0", "2022"), ("2022", "9")):
            cal = [d for d in cal_all if lo <= d < hi]
            print(f"--- block {blk} days, {'2018-21' if lo == '0' else '2022-25'}")
            for line in M.summary(M.compare(V, cal, trials=3000, seed=5), "now"):
                print("   " + line)
    print("--- original walk (one history, every start day), common calendar")
    for name, tr in V.items():
        res = []
        for lo, hi in (("0", "2022"), ("2022", "9")):
            c = [d for d in cal_all if lo <= d < hi]
            dd = days_for(tr, c, 1, 10 ** 9, ("ORB", "VG", "Z", "RS", "OD"))
            sz = lambda room: (1.0, 10 ** 9)
            f1 = outcomes(dd, sz, window=300, start_pnl=0.0, target=4000.0, consistency=False)
            rp = outcomes(dd, sz, window=300, start_pnl=2000.0, target=4000.0, consistency=False, locked=100.0)
            res.append(life(f1, rp))
        print(f"   {name:<16} ${res[0]:8,.0f} | ${res[1]:8,.0f}")


if __name__ == "__main__":
    main()
