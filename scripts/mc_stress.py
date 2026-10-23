"""Stress test of the funded proposal: extra slippage on every stop exit
(+1 NQ point per MNQ = $2) and on every trade (+0.5 pt), today's book vs the
proposal (VG + Z without gate + RS, no ORB), paired bootstrap.
Stop exits are known for VG / Z (live-spec 'SL' / 'STOP'); for ORB and RS the
stop share is unknown here, so every losing trade of those legs gets the extra.
Usage: mc_stress.py DATA_DIR
"""
from __future__ import annotations

import sys

sys.path.insert(0, "scripts")
import timed_book as TB  # noqa: E402
import gate_check as G  # noqa: E402
from score_live_spec import parse as parse_ls  # noqa: E402
from mc_book import compare, summary  # noqa: E402
from mc_runs import sized  # noqa: E402


def stops_set(data):
    T = parse_ls([f"{data}/LSVWAP_tags.txt", f"{data}/LSNOISE_tags.txt"])
    out = set()
    for k in ("B5", "NS"):
        for t in T[k]:
            if t["why"] in ("SL", "STOP"):
                out.add((t["date"], t["ehm"], round(t["pts"] * 2.0, 4)))
    return out


def stress(tr, stops, per_stop, per_trade):
    out = []
    for d, e, x, usd, leg in tr:
        hit = (d, e, round(usd, 4)) in stops if leg in ("VG", "Z") else usd < 0
        out.append((d, e, x, usd - per_trade - (per_stop if hit else 0.0), leg))
    return out


def main():
    data = sys.argv[1]
    base = G.build(data, set())
    zfree = G.build(data, {"Z"})
    stops = stops_set(data)
    cal_all = sorted({t[0] for t in base + zfree})
    for lab, ps, pt in (("normal costs", 0.0, 0.0), ("+1 pt on stops", 2.0, 0.0), ("+1 pt on stops, +0.5 pt every trade", 2.0, 1.0)):
        for lo, hi in (("0", "2022"), ("2022", "9")):
            cal = [d for d in cal_all if lo <= d < hi]
            V = {"now (ORB+VG+Z+RS)": sized(stress(base, stops, ps, pt), {"ORB": 3, "VG": 3, "Z": 3, "RS": 3}),
                 "proposal (VG+Zfree+RS)": sized(stress(zfree, stops, ps, pt), {"VG": 3, "Z": 3, "RS": 3})}
            print(f"--- {lab}, {'2018-21' if lo == '0' else '2022-25'}")
            for line in summary(compare(V, cal, trials=2500, seed=71), "now (ORB+VG+Z+RS)"):
                print("   " + line)


if __name__ == "__main__":
    main()
