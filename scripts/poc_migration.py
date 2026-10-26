"""Developing POC migration (day shift 2026-10-26, fixed before results).
Developing POC = price bin (0.05% of the open) with the most volume, each
5-min bar's volume placed at its typical price (h + l + c) / 3.
At 12:00 ET: shift = POC(09:30-12:00) - POC(09:30-10:00), in % of the open.
shift >= +0.10% -> LONG from the 12:00 close to 15:55; <= -0.10% -> SHORT.
Control: plain momentum (sign of the 10:00 -> 12:00 return) on the same days,
and POC vs momentum disagreeing. Gross bp, four eras + 2026.
Usage: poc_migration.py DATA_DIR
"""
from __future__ import annotations

import sys

sys.path.insert(0, "scripts")
import big_trades as B  # noqa: E402
import level_lab as L  # noqa: E402


def poc(b, n, o):
    w = o * 0.0005
    vol = {}
    for x in b[:n]:
        k = round(((x[1] + x[2] + x[3]) / 3) / w)
        vol[k] = vol.get(k, 0.0) + x[4]
    return max(vol, key=vol.get) * w


def main():
    days = B.load(sys.argv[1])
    for lab, lo, hi in B.ERAS:
        sig, mom, dis = [], [], []
        for d, b in days:
            if not (lo <= d < hi):
                continue
            o = b[0][0]
            sh = (poc(b, 30, o) - poc(b, 6, o)) / o
            r = (b[L.EOD][3] / b[29][3] - 1) * 1e4
            m = 1 if b[29][3] > b[5][3] else -1
            if abs(sh) >= 0.001:
                dd = 1 if sh > 0 else -1
                sig.append((d, dd * r))
                mom.append((d, m * r))
                if dd != m:
                    dis.append((d, dd * r))
        print(f"{lab:<8} n {len(sig):4d} | POC shift {B.stat(sig)} | momentum same days {B.stat(mom)} | POC when it disagrees with momentum (n {len(dis)}) {B.stat(dis)}")


if __name__ == "__main__":
    main()
