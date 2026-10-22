"""Overnight long after N down closes (NQ): buy the 15:55 close, sell the next
09:30 open. Rules fixed before looking: N = 3 (also 2 and 4 shown), baseline =
every night. Built from MFEAT (15:55 close = price + eod; open = 10:00 price /
(1 + return since open)). Cost 1 point per round trip.

Usage: overnight_after_downs.py SCRATCH_DIR
"""
from __future__ import annotations

import math
import statistics as st
import sys

sys.path.insert(0, "scripts")
from score_multi_feature import parse  # noqa: E402


def stat(v):
    if len(v) < 3:
        return f"{'n<3':>22}"
    sd = st.pstdev(v)
    return f"{st.mean(v):+6.2f} bp t{st.mean(v) / sd * math.sqrt(len(v)):+5.1f} n{len(v):>4} WR {sum(x > 0 for x in v) / len(v) * 100:3.0f}%"


def main():
    rows = parse(f"{sys.argv[1]}/MFEAT_tags.txt")
    day = {}
    for r in rows:
        d = day.setdefault(r["date"], {})
        d["close"] = r["e"] + r["eod"]
        if r["hm"] == 600:
            d["open"] = r["e"] / (1 + r["ret"])
    ds = [d for d in sorted(day) if "open" in day[d]]
    nights = []                       # (date of the close, down streak, overnight bp)
    for i in range(1, len(ds) - 1):
        c, n_open = day[ds[i]]["close"], day[ds[i + 1]]["open"]
        k = 0
        while i - k >= 1 and day[ds[i - k]]["close"] < day[ds[i - k - 1]]["close"]:
            k += 1
        cost = 1.0 / c * 1e4
        nights.append((ds[i], k, (n_open / c - 1) * 1e4 - cost))
    print(f"{'rule':<22} {'2018-2021':>34} | {'2022-2025':>34}")
    for lab, fn in (("every night", lambda k: True), ("after 2+ down", lambda k: k >= 2),
                    ("after 3+ down", lambda k: k >= 3), ("after 4+ down", lambda k: k >= 4),
                    ("after an up close", lambda k: k == 0)):
        a = [x for d, k, x in nights if d < "2022" and fn(k)]
        b = [x for d, k, x in nights if d >= "2022" and fn(k)]
        print(f"{lab:<22} {stat(a):>34} | {stat(b):>34}")
    sel = [(d, x) for d, k, x in nights if k >= 3]
    print("3+ down by year: " + "  ".join(f"{y} {st.mean([x for d, x in sel if d[:4] == y]):+.1f}"
                                          f"({sum(1 for d, _ in sel if d[:4] == y)})" for y in sorted({d[:4] for d, _ in sel})))


if __name__ == "__main__":
    main()
