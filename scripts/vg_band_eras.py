"""Lucid 2 VWAP band width 0.15 / 0.20 (live) / 0.25% in four eras: gross and net
bp per trade (B5 = first band break a day, SL 25 / TP 100 pt, not Wednesday,
vol gate). 2026-10-23.
Usage: vg_band_eras.py DATA_DIR
"""
from __future__ import annotations

import sys

sys.path.insert(0, "scripts")
from bp_eras import rows, stat, ERAS  # noqa: E402

FILES = {"0.15%": ["VG15_OLD", "VG15_NEW"], "0.20% (live)": ["LSVWAP_OLD", "LSVWAP"], "0.25%": ["VG25_OLD", "VG25_NEW"]}


def main():
    data = sys.argv[1]
    print("VWAP band B5, bp per trade: gross (net), vol gate on")
    for lab, files in FILES.items():
        R = [r for r in rows(data, files, "B5") if 0 < r[3] < 0.30]
        cells = []
        for e, lo, hi in ERAS:
            v = [r for r in R if lo <= r[0] < hi]
            cells.append(f"{e}: {stat([g for _, g, _, _ in v])} ({stat([g - c for _, g, c, _ in v])}) n{len(v)}")
        print(f"{lab:<13} " + " | ".join(cells))


if __name__ == "__main__":
    main()
