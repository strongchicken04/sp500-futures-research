"""Pool yearly in-QC late-flow aggregates ("YYYY LF G = +m bp/+t/n wins w")
into a pooled mean, approximate t (from per-year mean and t) and positive
years per group. Usage: pool_lflow.py RAW_FILE"""
from __future__ import annotations

import math
import re
import sys


def main():
    rows = {}
    for line in open(sys.argv[1]):
        m = re.match(r"(\d{4}) LF (\S+) = ([+-]\d+\.\d)bp/([+-]\d+\.\d)/(\d+) wins (\d+)", line.strip())
        if m:
            y, g, mean, t, n, w = m.groups()
            rows.setdefault(g, {})[y] = (float(mean), float(t), int(n), int(w))
    for g in ("ALL", "AGR", "DIV", "AGRs", "DIVs", "FLW", "STR+", "STR-", "STRs+", "STRs-", "WK-", "WK+", "C10", "C10s"):
        v = rows.get(g)
        if not v:
            continue
        N = sum(x[2] for x in v.values())
        mean = sum(x[0] * x[2] for x in v.values()) / N
        var = sum(((x[0] / x[1]) ** 2 * x[2] if x[1] else 0.0) * x[2] for x in v.values())   # se^2 * n^2 per year
        t = mean * N / math.sqrt(var) if var > 0 else 0.0
        pos = sum(x[0] > 0 for x in v.values())
        yrs = " ".join(f"{y[2:]}:{x[0]:+.1f}" for y, x in sorted(v.items()))
        print(f"{g:6s} pooled {mean:+5.1f} bp t {t:+4.1f} n {N:4d} win {sum(x[3] for x in v.values()) / N * 100:3.0f}%  +years {pos}/{len(v)}  {yrs}")


if __name__ == "__main__":
    main()
