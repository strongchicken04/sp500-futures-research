"""Midday fade (day shift 2026-10-26, fixed before results). Idea (Importer,
2026-10-26): since 0DTE options took over SPX volume (2023+), practitioners
(Susquehanna, JPMorgan quants, 2023) report more intraday REVERSAL - morning
moves faded in the afternoon - which would also explain why noise momentum
(Lucid 6) has had no edge since 2025.

Rules: at the close of the 5-min bar ending 12:00 ET, r = close / 09:30 open - 1.
If |r| > THR: trade AGAINST r (short after an up morning), entry at that
close, stop 0.50% of the entry, exit at 15:55 (variant EOD) or at a target
half way back to the 09:30 open (variant HALF). THR 0.30 / 0.50 / 0.75%.
Timing check (6c): signal bar ending 11:55 / 12:00 / 12:05 and 13:00.
Reported: GROSS bp per trade (no costs; costs ~1.4 bp at today's NQ), t, n,
by era 2010-13 / 2014-17 / 2018-21 / 2022 / 2023-24 / 2025-26 (0DTE split).
Positive = fade works; negative = momentum (go with the morning) works.
Usage: midday_fade.py DATA_DIR
"""
from __future__ import annotations

import math
import statistics as st
import sys

sys.path.insert(0, "scripts")
import level_lab as L  # noqa: E402

ERAS = (("2010-13", "2010", "2014"), ("2014-17", "2014", "2018"), ("2018-21", "2018", "2022"),
        ("2022", "2022", "2023"), ("2023-24", "2023", "2025"), ("2025-26", "2025", "2027"))
SIG = {"11:55": 28, "12:00": 29, "12:05": 30, "13:00": 41}


def trade(b, k, thr, variant):
    o = b[0][0]
    c = b[k][3]
    r = c / o - 1.0
    if abs(r) <= thr:
        return None
    d = -1 if r > 0 else 1
    stop = c * (1 - d * 0.005)
    tgt = c + d * abs(c - o) * 0.5 if variant == "HALF" else None
    for j in range(k + 1, L.EOD + 1):
        op, h, lo, cl, _ = b[j]
        if (d == 1 and lo <= stop) or (d == -1 and h >= stop):
            x = min(stop, op) if d == 1 else max(stop, op)
            return d * (x - c) / c * 1e4
        if tgt is not None and ((d == 1 and h >= tgt) or (d == -1 and lo <= tgt)):
            return d * (tgt - c) / c * 1e4
    return d * (b[L.EOD][3] - c) / c * 1e4


def main():
    data = sys.argv[1]
    days = []
    for names in (("B2_0A", "B2_0B"), ("BARS5A", "BARS5B"), ("B2_26",)):
        L.NAMES = names
        days += L.load(data)
    by = {}
    for dd in days:
        by[dd["date"]] = dd            # later panels overwrite overlapping dates
    days = [by[d] for d in sorted(by)]
    print(f"days {len(days)}: {days[0]['date']} .. {days[-1]['date']}")
    for variant in ("EOD", "HALF"):
        for sname, k in SIG.items():
            for thr in (0.003, 0.005, 0.0075):
                cells = []
                for lab, lo, hi in ERAS:
                    v = [x for x in (trade(dd["bars"], k, thr, variant) for dd in days if lo <= dd["date"] < hi) if x is not None]
                    if len(v) > 2:
                        t = st.mean(v) / (st.pstdev(v) / math.sqrt(len(v))) if st.pstdev(v) else 0
                        cells.append(f"{lab} {st.mean(v):+5.1f} (t{t:+4.1f}, n{len(v):3d})")
                print(f"   {variant:<4} {sname} thr {thr * 100:.2f}%: " + " | ".join(cells))


if __name__ == "__main__":
    main()
