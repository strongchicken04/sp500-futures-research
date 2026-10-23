"""Two calendar effects, four eras (night shift 2026-10-23/24, fixed before
results). Intraday only (09:31 entry -> 15:55, as the T931 rows of the
cond-bracket exports CBA_OLD / CBA), gross bp of price:
  PREHOL  long on the trading day before a weekday market holiday (a weekday
          missing from the calendar; the classic pre-holiday drift)
  MEREB   last trading day of the month: month-to-date return (prior close vs
          the previous month's last close) > +3% -> short, < -3% -> long
          (month-end rebalancing flows)
Baseline: all days long (drift). t-stat of the mean.
Usage: calendar_lab.py DATA_DIR
"""
from __future__ import annotations

import datetime as dt
import math
import statistics as st
import sys

sys.path.insert(0, "scripts")
from score_cond_bracket import parse  # noqa: E402

ERAS = (("2010-13", "2010", "2014"), ("2014-17", "2014", "2018"), ("2018-21", "2018", "2022"), ("2022-25", "2022", "2026"))


def stat(v):
    if len(v) < 3:
        return f"n {len(v)}"
    sd = st.pstdev(v) or 1.0
    return f"{st.mean(v):+6.1f} bp t{st.mean(v) / sd * math.sqrt(len(v)):+4.1f} n{len(v):>4}"


def main():
    data = sys.argv[1]
    rows = sorted([r for f in ("CBA_OLD", "CBA") for r in parse([f"{data}/{f}_tags.txt"]) if r["type"] == "T931"], key=lambda r: r["date"])
    dates = [r["date"] for r in rows]
    ds = set(dates)
    ret = {r["date"]: r["eod"] / r["e"] * 1e4 for r in rows}
    out = {"ALL": {}, "PREHOL": {}, "MEREB": {}}
    for i, r in enumerate(rows):
        d = dt.date.fromisoformat(r["date"])
        out["ALL"][r["date"]] = ret[r["date"]]
        nxt = d + dt.timedelta(days=1)
        while nxt.weekday() >= 5:
            nxt += dt.timedelta(days=1)
        if nxt.isoformat() not in ds and nxt.isoformat() < dates[-1]:
            out["PREHOL"][r["date"]] = ret[r["date"]]
        if i + 1 < len(rows) and rows[i + 1]["date"][:7] != r["date"][:7] and i > 25:
            # previous month's last close = pc of this month's first trading day
            first = next(x for x in rows[i - 25:i + 1] if x["date"][:7] == r["date"][:7])
            mtd = r["pc"] / first["pc"] - 1.0
            if mtd > 0.03:
                out["MEREB"][r["date"]] = -ret[r["date"]]
            elif mtd < -0.03:
                out["MEREB"][r["date"]] = ret[r["date"]]
    for k, v in out.items():
        print(f"{k:<7} " + " | ".join(f"{lab} {stat([x for d, x in v.items() if lo <= d < hi])}" for lab, lo, hi in ERAS))


if __name__ == "__main__":
    main()
