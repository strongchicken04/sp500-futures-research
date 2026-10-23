"""Edge per trade in basis points of price, gross and net (0.75 pt + 0.25 pt on
stops per micro, converted at the trade's price), for the live legs in four
eras: 2010-13, 2014-17 (untouched), 2018-21 (tuning), 2022-25 (test).
Usage: bp_eras.py DATA_DIR
"""
from __future__ import annotations

import math
import statistics as st
import sys

ERAS = (("2010-13", "2010", "2014"), ("2014-17", "2014", "2018"), ("2018-21", "2018", "2022"), ("2022-25", "2022", "2026"))
SRC = {"ORB": (["LSORB_OLD", "LSORB_A", "LSORB_B"], "O5"), "VG": (["LSVWAP_OLD", "LSVWAP"], "B5"),
       "Z": (["LSNOISE_OLD", "LSNOISE"], "NS")}


def rows(data, files, var):
    out = []
    for f in files:
        try:
            fh = open(f"{data}/{f}_tags.txt")
        except FileNotFoundError:
            continue
        for raw in fh:
            p = raw.strip().split(",")
            if p[0] != "L" or len(p) < 10 or p[1] != var:
                continue
            d, e, x = int(p[3]), float(p[5]), float(p[7])
            cost = 0.75 + (0.25 if p[8] in ("SL", "STOP") else 0.0)
            out.append((f"{p[2][:4]}-{p[2][4:6]}-{p[2][6:]}", d * (x - e) / e * 1e4, cost / e * 1e4, int(p[9]) / 1000.0))
    return out


def stat(v):
    if len(v) < 3:
        return "n<3"
    sd = st.pstdev(v)
    return f"{st.mean(v):+6.2f} t{st.mean(v) / sd * math.sqrt(len(v)):+4.1f}"


def main():
    data = sys.argv[1]
    print("bp per trade: gross (net)   [vol gate on; Z also without]")
    for leg, (files, var) in SRC.items():
        R = rows(data, files, var)
        for gate in ((True, False) if leg == "Z" else (True,)):
            cells = []
            for lab, lo, hi in ERAS:
                v = [r for r in R if lo <= r[0] < hi and (not gate or 0 < r[3] < 0.30)]
                cells.append(f"{lab}: {stat([g for _, g, _, _ in v])} ({stat([g - c for _, g, c, _ in v])}) n{len(v)}")
            print(f"{leg}{'' if gate else ' nogate':<8} " + " | ".join(cells))


if __name__ == "__main__":
    main()
