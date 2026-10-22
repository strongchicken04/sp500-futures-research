"""Turn-of-month effect on NQ (Carchano & Pardo; Lakonishok & Smidt).
Rules fixed before looking: TOM window = last trading day of the month and
the first three trading days of the next. Two ways to hold:
  rth        long 09:30 open to 15:55 close on each TOM day
  cc         long the 15:55 close of the day before the window to the 15:55
             close of the window's last day (one trade a month)
Baseline: the same on all other days / an equal-length random-start hold is
approximated by the non-TOM daily mean. Cost 1 point per round trip.
Data: MFEAT (open = 10:00 price / (1 + return since open), close = price + eod).

Usage: turn_of_month.py SCRATCH_DIR
"""
from __future__ import annotations

import math
import statistics as st
import sys

sys.path.insert(0, "scripts")
from score_multi_feature import parse  # noqa: E402


def stat(v):
    if len(v) < 3:
        return "n<3"
    sd = st.pstdev(v)
    return f"{st.mean(v):+6.1f} bp t{st.mean(v) / sd * math.sqrt(len(v)):+4.1f} n{len(v):>4} WR {sum(x > 0 for x in v) / len(v) * 100:3.0f}%"


def main():
    day = {}
    for r in parse(f"{sys.argv[1]}/MFEAT_tags.txt"):
        d = day.setdefault(r["date"], {})
        d["close"] = r["e"] + r["eod"]
        if r["hm"] == 600:
            d["open"] = r["e"] / (1 + r["ret"])
    ds = [d for d in sorted(day) if "open" in day[d]]
    tom = set()
    for i in range(len(ds) - 1):
        if ds[i][:7] != ds[i + 1][:7]:              # ds[i] is a month's last day
            tom.update(ds[max(0, i):i + 4])
    rth = {d: (day[d]["close"] / day[d]["open"] - 1) * 1e4 - 1 / day[d]["open"] * 1e4 for d in ds}
    cc = []
    for i in range(1, len(ds) - 3):
        if ds[i][:7] != ds[i + 1][:7]:
            c0, c1 = day[ds[i - 1]]["close"], day[ds[i + 3]]["close"]
            cc.append((ds[i], (c1 / c0 - 1) * 1e4 - 1 / c0 * 1e4))
    c2c = {ds[i]: (day[ds[i]]["close"] / day[ds[i - 1]]["close"] - 1) * 1e4 for i in range(1, len(ds))}
    for lab, lo, hi in (("2018-2021", "0", "2022"), ("2022-2025", "2022", "9")):
        print(f"--- {lab}")
        print(f"  rth on TOM days      {stat([x for d, x in rth.items() if d in tom and lo <= d < hi])}")
        print(f"  rth on other days    {stat([x for d, x in rth.items() if d not in tom and lo <= d < hi])}")
        print(f"  close-close TOM day  {stat([x for d, x in c2c.items() if d in tom and lo <= d < hi])}")
        print(f"  close-close other    {stat([x for d, x in c2c.items() if d not in tom and lo <= d < hi])}")
        print(f"  4-day TOM hold       {stat([x for d, x in cc if lo <= d < hi])}")
    print("4-day hold by year: " + "  ".join(f"{y} {st.mean([x for d, x in cc if d[:4] == y]):+.0f}" for y in sorted({d[:4] for d, _ in cc})))


if __name__ == "__main__":
    main()
