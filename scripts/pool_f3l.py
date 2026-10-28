"""Pool yearly in-QC F3 x location aggregates ("YYYY F3L G = +m/+t/n stops k")
into a pooled mean (gross bp), approximate t and positive years per group.
Usage: pool_f3l.py RAW_FILE"""
from __future__ import annotations

import math
import re
import sys


def main():
    rows = {}
    for line in open(sys.argv[1]):
        m = re.match(r"(\d{4}) F3L (\S+) = ([+-]\d+\.\d)/([+-]\d+\.\d)/(\d+) stops (\d+)", line.strip())
        if m:
            y, g, mean, t, n, k = m.groups()
            rows.setdefault(g, {})[y] = (float(mean), float(t), int(n), int(k))
    for g in ("ALL", "L_LOW", "L_MID", "L_HIGH", "S_HIGH", "S_MID", "S_LOW"):
        v = rows.get(g)
        if not v:
            continue
        N = sum(x[2] for x in v.values())
        mean = sum(x[0] * x[2] for x in v.values()) / N
        var = sum(((x[0] / x[1]) ** 2 * x[2] if x[1] else 0.0) * x[2] for x in v.values())
        t = mean * N / math.sqrt(var) if var > 0 else 0.0
        pos = sum(x[0] > 0 for x in v.values())
        yrs = " ".join(f"{y[2:]}:{x[0]:+.1f}" for y, x in sorted(v.items()))
        print(f"{g:6s} pooled {mean:+5.2f} bp t {t:+4.1f} n {N:5d}  +years {pos}/{len(v)}  {yrs}")


if __name__ == "__main__":
    main()
