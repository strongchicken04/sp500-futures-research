"""Follow-up of big_trades.py (post-hoc, so it must hold everywhere): FADE a
bubble that agrees with the trend since the open AND the VWAP side (a
climactic push in the trend direction). Plateau R 2 / 3 / 4 x F 0.70 / 0.80 /
0.90, fade gross bp after 15 and 30 min, four eras + 2026.
Usage: big_trades_fade.py DATA_DIR
"""
from __future__ import annotations

import sys

sys.path.insert(0, "scripts")
import big_trades as B  # noqa: E402


def main():
    days = B.load(sys.argv[1])
    ev_all = B.events(days)
    both = lambda e, d: d * (e[4][e[1]][3] - e[5]) > 0 and d * e[6] > 0
    B.HOR = (("15m", 3), ("30m", 6))
    for R in (2, 3, 4):
        for F in (0.70, 0.80, 0.90):
            cells = []
            for lab, lo, hi in B.ERAS:
                ev = [e for e in ev_all if lo <= e[0] < hi]
                row = B.table(ev, "", R, F, both)
                cells.append(f"{lab} {row.split('|', 1)[1].strip()}")
            print(f"R{R} F{F:.2f} (WITH the bubble; fade = minus): " + " || ".join(cells))


if __name__ == "__main__":
    main()
