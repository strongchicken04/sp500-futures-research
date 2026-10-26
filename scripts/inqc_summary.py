"""Table of the in-QC big-trades aggregates (results/bubbles_inqc_raw.txt):
mean bp (t) by year for each variant and horizon, plus how many years are
positive / significant. Usage: inqc_summary.py RAW_FILE"""
from __future__ import annotations

import re
import sys


def main():
    rows = {}
    for line in open(sys.argv[1]):
        m = re.match(r"(\d{4}) (R\d) (\w+) = (.*)", line.strip())
        if not m:
            continue
        y, r, f, rest = m.groups()
        for h, mean, t, n in re.findall(r"(\d+)m ([+-]\d+\.\d)/([+-]\d+\.\d)/(\d+)", rest):
            if int(n) >= 20:
                rows.setdefault((r, f, int(h)), {})[y] = (float(mean), float(t))
    years = sorted({y for v in rows.values() for y in v})
    print("variant              h   " + "  ".join(f"{y:>11}" for y in years) + "   pos  |t|>=2")
    for (r, f, h), v in sorted(rows.items()):
        cells = [f"{v[y][0]:+5.1f}({v[y][1]:+4.1f})" if y in v else " " * 11 for y in years]
        pos = sum(1 for x in v.values() if x[0] > 0)
        sig = sum(1 for x in v.values() if abs(x[1]) >= 2)
        print(f"{r} {f:<8} {h:>3}m  " + "  ".join(cells) + f"   {pos}/{len(v)}  {sig}")


if __name__ == "__main__":
    main()
