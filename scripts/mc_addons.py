"""Core candidate book (VG + Z without gate + RS, flat 3) with the two add-on
candidates of the day: open drive (OD) and NR4 breakout (NR), alone and
together; paired bootstrap, plus their daily correlation.
Usage: mc_addons.py DATA_DIR
"""
from __future__ import annotations

import statistics as st
import sys
from collections import defaultdict

sys.path.insert(0, "scripts")
import level_lab as L  # noqa: E402
import gate_check as G  # noqa: E402
from mc_simple import nr4  # noqa: E402
from mc_book import compare, summary  # noqa: E402
from mc_runs import sized  # noqa: E402
from rescore_all import rvol  # noqa: E402


def main():
    data = sys.argv[1]
    base = [t for t in G.build(data, {"Z"}) if t[4] in ("VG", "Z", "RS")]
    days = L.load(data)
    reg = rvol()
    new = []
    for leg, fn in (("NR", nr4(days)), ("OD", lambda d, p: L.odrive(d, p, 0.0005, 0.0015))):
        new += [(t["date"], t["ehm"], t["xhm"], t["pts"] * 2.0, leg) for t in L.trades(days, fn) if reg.get(t["date"], 9.0) < 0.30]
    tr = base + new
    cal_all = sorted({t[0] for t in tr})
    nr_days = {t[0] for t in new if t[4] == "NR"}
    od_days = {t[0] for t in new if t[4] == "OD"}
    dd = {k: defaultdict(float) for k in ("NR", "OD", "Z")}
    for t in tr:
        if t[4] in dd:
            dd[t[4]][t[0]] += t[3]
    print("daily corr NR-OD %+.2f, NR-Z %+.2f, OD-Z %+.2f; same-day NR & OD trades: %d" % (
        st.correlation([dd["NR"][d] for d in cal_all], [dd["OD"][d] for d in cal_all]),
        st.correlation([dd["NR"][d] for d in cal_all], [dd["Z"][d] for d in cal_all]),
        st.correlation([dd["OD"][d] for d in cal_all], [dd["Z"][d] for d in cal_all]),
        len(nr_days & od_days)))
    core = {"VG": 3, "Z": 3, "RS": 3}
    for lo, hi in (("0", "2022"), ("2022", "9")):
        cal = [d for d in cal_all if lo <= d < hi]
        V = {"core VG+Zfree+RS": sized(tr, core), "+ OD 3": sized(tr, dict(core, OD=3)), "+ NR4 3": sized(tr, dict(core, NR=3)),
             "+ OD 3 + NR4 3": sized(tr, dict(core, OD=3, NR=3)), "+ OD 2 + NR4 2": sized(tr, dict(core, OD=2, NR=2))}
        print(f"--- {'2018-2021' if lo == '0' else '2022-2025'}")
        for line in summary(compare(V, cal, trials=3000, seed=61), "core VG+Zfree+RS"):
            print("   " + line)


if __name__ == "__main__":
    main()
