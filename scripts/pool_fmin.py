"""Pool yearly in-QC first-minute aggregates ("YYYY FM G = win w/r +m bp/+t/n"):
resolved win rate vs the random-walk rate 0.40 / 0.65 = 61.5% (z on the pooled
binomial), mean gross bp, years above random. Usage: pool_fmin.py RAW_FILE"""
from __future__ import annotations

import math
import re
import sys

RW = 0.40 / 0.65


def main():
    rows = {}
    for line in open(sys.argv[1]):
        m = re.match(r"(\d{4}) FM (\S+) = win (\d+)/(\d+) ([+-]\d+\.\d)bp/([+-]\d+\.\d)/(\d+)", line.strip())
        if m:
            y, g, w, r, mean, t, n = m.groups()
            rows.setdefault(g, {})[y] = (int(w), int(r), float(mean), int(n))
    for g in ("PX", "FLOW", "F10", "F20", "AGREE", "CLASH"):
        v = rows.get(g)
        if not v:
            continue
        W, R = sum(x[0] for x in v.values()), sum(x[1] for x in v.values())
        N = sum(x[3] for x in v.values())
        mean = sum(x[2] * x[3] for x in v.values()) / N
        z = (W / R - RW) / math.sqrt(RW * (1 - RW) / R) if R else 0.0
        above = sum(x[0] / x[1] > RW for x in v.values() if x[1])
        yrs = " ".join(f"{y[2:]}:{x[0] / x[1] * 100:.0f}%" for y, x in sorted(v.items()) if x[1])
        print(f"{g:5s} resolved win {W / R * 100:4.1f}% (random 61.5%, z {z:+4.1f}) n {R:4d}  mean {mean:+5.1f} bp  "
              f"above random {above}/{len(v)}  {yrs}")


if __name__ == "__main__":
    main()
