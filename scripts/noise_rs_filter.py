"""Noise momentum filtered by relative strength (pre-specified): a noise trade
counts as 'agreeing' when NQ's return since the open minus ES's has the same
sign as the trade at the entry check (from the 5-minute RS export; entries
after 15:00 have no RS reading and are shown separately). Lucid 6 live rules
with the hard stop (LSNOISE NS), NQ points per MNQ net.

Usage: noise_rs_filter.py SCRATCH_DIR
"""
from __future__ import annotations

import math
import statistics as st
import sys

sys.path.insert(0, "scripts")
from score_live_spec import parse as parse_ls  # noqa: E402
from score_rs_variants import parse as parse_rs  # noqa: E402


def stat(v):
    if len(v) < 3:
        return "n<3"
    sd = st.pstdev(v)
    return f"{st.mean(v):+6.2f} pt t{st.mean(v) / sd * math.sqrt(len(v)):+4.1f} n{len(v):>4}"


def main():
    sp = sys.argv[1]
    T = parse_ls([f"{sp}/LSNOISE_tags.txt"])
    days = parse_rs([f"{sp}/RSVA_tags.txt", f"{sp}/RSVB_tags.txt"])
    rs_at = {(d, r["hm"]): r["es"] for d, day in days.items() for r in day["rows"]}
    raw = {}
    for line in open(f"{sp}/LSNOISE_tags.txt"):
        f = line.strip().split(",")
        if f[0] == "L" and f[1] == "NS":
            raw[(f"{f[2][:4]}-{f[2][4:6]}-{f[2][6:]}", int(f[4]))] = int(f[3])
    groups = {}
    for t in T["NS"]:
        if not (0 < t["rv"] < 0.30):
            continue
        side = raw.get((t["date"], t["ehm"]), 0)
        r = rs_at.get((t["date"], t["ehm"]))
        g = "no RS reading (after 15:00)" if r is None else ("RS agrees" if r * side > 0 else ("RS disagrees" if r * side < 0 else "RS zero"))
        groups.setdefault(g, {"a": [], "b": []})["a" if t["date"] < "2022" else "b"].append(t["pts"])
    for g, v in sorted(groups.items()):
        print(f"{g:<28} 2018-21 {stat(v['a'])}  |  2022-25 {stat(v['b'])}")


if __name__ == "__main__":
    main()
