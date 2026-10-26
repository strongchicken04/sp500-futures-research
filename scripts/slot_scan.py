"""Half-hour slot scan (day shift 2026-10-26, fixed before results; a scan, so
only a sign that holds in ALL four eras with |t| >= 2 in at least three
counts). For each 30-min slot from 10:00 to 16:00 ET (bars 6-11, 12-17, ...):
  U  unconditional slot return (gross bp)
  M  slot return x sign(return from the 09:30 open to the slot start)
     (> 0 = intraday momentum into that slot, < 0 = reversal)
Day = one observation. Four eras + 2026.
Usage: slot_scan.py DATA_DIR
"""
from __future__ import annotations

import math
import statistics as st
import sys

sys.path.insert(0, "scripts")
import big_trades as B  # noqa: E402


def tt(v):
    return st.mean(v) / (st.pstdev(v) / math.sqrt(len(v))) if len(v) > 2 and st.pstdev(v) else 0.0


def main():
    days = B.load(sys.argv[1])
    for j in range(6, 78, 6):
        s0, s1 = j - 1, j + 5           # slot from the close of bar j-1 to the close of bar j+5
        h0 = 9 * 60 + 30 + 5 * j
        cells_u, cells_m = [], []
        for lab, lo, hi in B.ERAS:
            u, m = [], []
            for d, b in days:
                if not (lo <= d < hi) or s1 >= len(b):
                    continue
                r = (b[s1][3] / b[s0][3] - 1) * 1e4
                pre = b[s0][3] / b[0][0] - 1
                u.append(r)
                if pre != 0:
                    m.append(r * (1 if pre > 0 else -1))
            cells_u.append(f"{st.mean(u):+5.1f}({tt(u):+4.1f})")
            cells_m.append(f"{st.mean(m):+5.1f}({tt(m):+4.1f})")
        print(f"{h0 // 60:02d}:{h0 % 60:02d}-{(h0 + 30) // 60:02d}:{(h0 + 30) % 60:02d}  U " + " ".join(cells_u) + "  |  M " + " ".join(cells_m))
    print("eras: " + " ".join(e[0] for e in B.ERAS))


if __name__ == "__main__":
    main()
