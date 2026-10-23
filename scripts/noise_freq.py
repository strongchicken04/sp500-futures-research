"""Noise momentum decision frequency (Lucid 6 rules, 0.50% hard stop): checks
every 15 / 30 (live) / 60 minutes, no vol gate. Per-day P&L per micro and the
funded book by paired bootstrap (VG + Z + RS, no ORB, flat 3) with each Z
variant, plus Z30 + Z60 at 2 MNQ each (fixed in advance, 2026-10-23).
Usage: noise_freq.py DATA_DIR
"""
from __future__ import annotations

import math
import statistics as st
import sys
from collections import defaultdict

sys.path.insert(0, "scripts")
import gate_check as G  # noqa: E402
from score_live_spec import parse as parse_ls  # noqa: E402
from mc_book import compare, summary  # noqa: E402
from mc_runs import sized  # noqa: E402

FILES = {"Z15": "LSNOISE_C15", "Z30": "LSNOISE", "Z60": "LSNOISE_C60"}


def main():
    data = sys.argv[1]
    base = [t for t in G.build(data, {"Z"}) if t[4] in ("VG", "RS")]
    Z = {}
    for k, f in FILES.items():
        T = parse_ls([f"{data}/{f}_tags.txt"])
        Z[k] = [(t["date"], t["ehm"], t["xhm"], t["pts"] * 2.0, k) for t in T["NS"]]
    cal_all = sorted({t[0] for t in base} | {t[0] for v in Z.values() for t in v})
    daily = {}
    for k, v in Z.items():
        dd = defaultdict(float)
        for t in v:
            dd[t[0]] += t[3]
        daily[k] = dd
        for lo, hi in (("0", "2022"), ("2022", "9")):
            days = [d for d in cal_all if lo <= d < hi]
            x = [dd.get(d, 0.0) for d in days]
            n = sum(1 for t in v if lo <= t[0] < hi)
            print(f"{k} {lo}-{hi}: trades {n}, ${sum(x) / len(days):+.2f} per day per micro, "
                  f"t {st.mean(x) / st.pstdev(x) * math.sqrt(len(x)):+.1f}")
    for a, b in (("Z15", "Z30"), ("Z30", "Z60"), ("Z15", "Z60")):
        print(f"daily corr {a}-{b}: {st.correlation([daily[a].get(d, 0) for d in cal_all], [daily[b].get(d, 0) for d in cal_all]):+.2f}")
    for lo, hi in (("0", "2022"), ("2022", "9")):
        cal = [d for d in cal_all if lo <= d < hi]
        V = {f"VG+RS+{k}": sized(base + Z[k], {"VG": 3, "RS": 3, k: 3}) for k in ("Z30", "Z15", "Z60")}
        V["VG+RS+Z30 2+Z60 2"] = sized(base + Z["Z30"] + Z["Z60"], {"VG": 3, "RS": 3, "Z30": 2, "Z60": 2})
        print(f"--- {'2018-2021' if lo == '0' else '2022-2025'}")
        for line in summary(compare(V, cal, trials=3000, seed=41), "VG+RS+Z30"):
            print("   " + line)


if __name__ == "__main__":
    main()
