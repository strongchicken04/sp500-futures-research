"""Pool yearly in-QC Z x flow aggregates: per group pooled points per trade,
approximate t, positive years; risk view (sum / max DD / worst 20 days) per
year for ALL vs C02 vs POS. Usage: pool_zflow.py RAW_FILE"""
from __future__ import annotations

import math
import re
import sys


def main():
    rows, risk = {}, {}
    for line in open(sys.argv[1]):
        line = line.strip()
        m = re.match(r"(\d{4}) Z (\S+) = ([+-]\d+\.\d)pt/([+-]\d+\.\d)/(\d+) wins (\d+)", line)
        if m:
            y, g, mean, t, n, w = m.groups()
            rows.setdefault(g, {})[y] = (float(mean), float(t), int(n), int(w))
        m = re.match(r"(\d{4}) ZR (\S+) = sum ([+-]\d+)pt maxDD (\d+)pt worst20d ([+-]\d+)pt", line)
        if m:
            y, g, s, dd, w20 = m.groups()
            risk.setdefault(y, {})[g] = (int(s), int(dd), int(w20))
    for g in ("ALL", "POS", "NEG", "C02", "A02", "C05", "A05"):
        v = rows.get(g)
        if not v:
            continue
        N = sum(x[2] for x in v.values())
        mean = sum(x[0] * x[2] for x in v.values()) / N
        var = sum(((x[0] / x[1]) ** 2 * x[2] if x[1] else 0.0) * x[2] for x in v.values())
        t = mean * N / math.sqrt(var) if var > 0 else 0.0
        yrs = " ".join(f"{y[2:]}:{x[0]:+.1f}" for y, x in sorted(v.items()))
        print(f"{g:4s} pooled {mean:+5.1f} pt t {t:+4.1f} n {N:4d}  +years {sum(x[0] > 0 for x in v.values())}/{len(v)}  {yrs}")
    print("risk (points per contract): sum / maxDD / worst 20 days   ALL | C02 | POS")
    for y in sorted(risk):
        r = risk[y]
        print(f"  {y}  " + " | ".join(f"{r[g][0]:+6d} / {r[g][1]:5d} / {r[g][2]:+5d}" if g in r else "-" for g in ("ALL", "C02", "POS")))


if __name__ == "__main__":
    main()
