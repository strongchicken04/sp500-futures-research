"""Day-type batch (night 2026-10-27/28, rules fixed before results), NQ 5-min
RTH, gross bp, four eras + 2026, day-clustered (one trade per day):
  LLS  mirror of the late-day long: prev close > SMA50, open < prev close
       -0.60%, at 15:00 close < open and range position < 0.23 -> SHORT
       15:00 -> 16:00, stop 1%
  IBS  prior-day RTH IBS = (close - low) / (high - low): < 0.20 -> LONG,
       > 0.80 -> SHORT, open -> 15:55 (Connors-style reversion, intraday only)
  IBSL IBS < 0.20 long only, and only when prev close > SMA200 (published
       QQQ form)
  STK  after 3+ down RTH closes (close < prev close) -> LONG open -> 15:55
       (intraday twin of the overnight-after-3-down rule)
  LL14 late-day long with entry at 14:00 (decomp found the effect from 14:00)
       -> only reported, NOT a new rule (post-hoc)
Usage: daytype_batch.py DATA_DIR
"""
from __future__ import annotations

import sys

sys.path.insert(0, "scripts")
import big_trades as B  # noqa: E402
import qqq_late_long as Q  # noqa: E402


def main():
    days = B.load(sys.argv[1])
    cl = [b[77][3] for _, b in days]
    out = {k: [] for k in ("LLS", "IBS", "IBSL", "STK", "LL14")}
    for i in range(200, len(days)):
        d, b = days[i]
        pb = days[i - 1][1]
        pc = cl[i - 1]
        sma50 = sum(cl[i - 50:i]) / 50
        sma200 = sum(cl[i - 200:i]) / 200
        op = b[0][0]
        # LLS
        if pc > sma50 and op < pc * 0.994:
            c = b[65][3]
            hi = max(x[1] for x in b[:66]); lo = min(x[2] for x in b[:66])
            if c < op and hi > lo and (c - lo) / (hi - lo) < 0.23:
                stop = any(x[1] >= c * 1.01 for x in b[66:78])
                out["LLS"].append((d, -100.0 if stop else -(b[77][3] / c - 1) * 1e4))
        # LL14 (post-hoc report)
        if pc < sma50 and op > pc * 1.006:
            c = b[53][3]
            hi = max(x[1] for x in b[:54]); lo = min(x[2] for x in b[:54])
            if c > op and hi > lo and (c - lo) / (hi - lo) > 0.77:
                stop = any(x[2] <= c * 0.99 for x in b[54:78])
                out["LL14"].append((d, -100.0 if stop else (b[77][3] / c - 1) * 1e4))
        # IBS
        ph = max(x[1] for x in pb); pl = min(x[2] for x in pb)
        if ph > pl:
            ibs = (pb[77][3] - pl) / (ph - pl)
            r = (b[76][3] / op - 1) * 1e4
            if ibs < 0.20:
                out["IBS"].append((d, r))
                if pc > sma200:
                    out["IBSL"].append((d, r))
            elif ibs > 0.80:
                out["IBS"].append((d, -r))
        # STK
        if all(cl[i - j] < cl[i - j - 1] for j in (1, 2, 3)):
            out["STK"].append((d, (b[76][3] / op - 1) * 1e4))
    print("eras:", " | ".join(e[0] for e in B.ERAS), "  (gross bp per trade, t, n)")
    for k, rs in out.items():
        print(f"{k:5s}", " ".join(Q.cell(v) for v in Q.by_era(rs)))


if __name__ == "__main__":
    main()
