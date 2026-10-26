"""Pool yearly in-QC RS x delta aggregates (mean / t / n per year) into one
mean, approximate t and the count of positive years per group.
Usage: pool_inqc.py RAW_FILE"""
from __future__ import annotations

import math
import re
import sys


def main():
    rows, seen = {}, set()
    for line in open(sys.argv[1]):
        m = re.match(r"(\d{4}) (\S+) = (.*)", line.strip())
        if not m:
            continue
        y, g, rest = m.groups()
        if (y, g) in seen:
            continue
        seen.add((y, g))
        for kind, mean, t, n, w in re.findall(r"(leg|sprint) ([+-]\d+\.\d)/([+-]\d+\.\d)/(\d+)(?: win (\d+/\d+))?", rest):
            rows.setdefault((g, kind), []).append((y, float(mean), float(t), int(n), w))
    order = ["o>=5", "o2-5", "o0-2", "a0-2", "a2-5", "a>=5", "against", "neutral", "agree", "all"]
    for kind in ("leg", "sprint"):
        print(f"--- {kind}")
        for g in order:
            v = [x for x in rows.get((g, kind), []) if "2019" <= x[0] <= "2026"]
            if not v:
                continue
            N = sum(x[3] for x in v)
            M = sum(x[1] * x[3] for x in v) / N
            S2 = sum(((abs(x[1]) * math.sqrt(x[3]) / abs(x[2])) ** 2 if x[2] else 0) * x[3] for x in v)
            sd = math.sqrt(S2 / N) if N else 0
            T = M / (sd / math.sqrt(N)) if sd else 0
            wins = [tuple(map(int, x[4].split("/"))) for x in v if x[4]]
            ww, rr = sum(a for a, b in wins), sum(b for a, b in wins)
            pos = sum(1 for x in v if x[1] > 0)
            extra = f" | resolved win {ww}/{rr} = {ww / rr * 100:.0f}%" if kind == "sprint" and rr else ""
            print(f"   {g:<8} {M:+6.1f} bp (t~{T:+4.1f}) n {N:4d} | years > 0: {pos}/{len(v)}{extra}")


if __name__ == "__main__":
    main()
