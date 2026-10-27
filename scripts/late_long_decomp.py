"""Where does the QQQ late-day long edge sit? (night 2026-10-27/28, fixed
before results). Day type D = previous RTH close < SMA50 and RTH open > prev
close +0.60% (rules 1-2 of qqq_late_long.py). Control C = gap up > 0.60% with
the previous close ABOVE the SMA50.
For entry at the close of the bar ending 10:00 / 12:00 / 14:00 / 15:00 (and
14:55 / 15:05) and exit 16:00 (no stop), gross bp, four eras + 2026:
  D any     day type only
  D strong  plus close > open and range position > 0.77 at the entry time
  C strong  same strength rules on control days
If D strong is positive at every entry time -> one effect (strong recovery
days in a downtrend keep going); if only 15:00 -> a 15:00 effect / fit.
Usage: late_long_decomp.py DATA_DIR
"""
from __future__ import annotations

import sys

sys.path.insert(0, "scripts")
import big_trades as B  # noqa: E402
import qqq_late_long as Q  # noqa: E402

TIMES = ((5, "10:00"), (29, "12:00"), (53, "14:00"), (64, "14:55"), (65, "15:00"), (66, "15:05"))


def main():
    days = B.load(sys.argv[1])
    closes = [b[77][3] for _, b in days]
    print("eras:", " | ".join(e[0] for e in B.ERAS), "  (gross bp, entry -> 16:00, no stop)")
    for k, lab in TIMES:
        out = {"D any": [], "D strong": [], "C strong": []}
        for i in range(50, len(days)):
            d, b = days[i]
            pc = closes[i - 1]
            if not b[0][0] > pc * 1.006:
                continue
            below = pc < sum(closes[i - 50:i]) / 50
            c = b[k][3]
            hi = max(x[1] for x in b[:k + 1])
            lo = min(x[2] for x in b[:k + 1])
            strong = c > b[0][0] and hi > lo and (c - lo) / (hi - lo) > 0.77
            r = (b[77][3] / c - 1) * 1e4
            if below:
                out["D any"].append((d, r))
                if strong:
                    out["D strong"].append((d, r))
            elif strong:
                out["C strong"].append((d, r))
        for name, rs in out.items():
            print(f"{lab} {name:9s}", " ".join(Q.cell(v) for v in Q.by_era(rs)))
        print()


if __name__ == "__main__":
    main()
