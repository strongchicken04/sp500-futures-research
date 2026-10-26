"""Fresh local ideas, batch 2 (day shift 2026-10-26, rules fixed before results).

V1 VIX DIVERGENCE (MFEAT rows at the 10:00 / 11:00 / 13:00 / 14:30 checks):
   NQ up > +0.30% since the open while VIX is UP vs its prior close (vixchg > 0)
   -> SHORT NQ; NQ down < -0.30% while VIX is DOWN -> LONG. First per day.
   Outcome from the check: to 15:55 (gross bp) and a +/-0.30% bracket.
   Four eras + 2026.
S1 SMT DIVERGENCE (5-min NQ + ES panels, 2018-25 only - no ES panel for
   2010-17 / 2026, so information only): bar k ending 10:05 .. 15:30 ET:
   ES makes a new session high (above all earlier RTH bars) and NQ does NOT
   -> SHORT NQ ("NQ lags, fade"); ES new low and NQ not -> LONG.
   Mirror S2: NQ new high and ES NOT -> LONG NQ (NQ leads, follow).
   First per day; forward 15 / 30 / 60 min and 15:55, day-clustered.
Usage: fresh_local2.py DATA_DIR
"""
from __future__ import annotations

import math
import statistics as st
import sys

sys.path.insert(0, "scripts")
import big_trades as B  # noqa: E402
import level_lab as L  # noqa: E402
from score_multi_feature import parse as parse_mf, LEVELS as ML, bp  # noqa: E402

ERAS4 = (("2010-13", "2010", "2014", "_OLD"), ("2014-17", "2014", "2018", "_OLD"), ("2018-21", "2018", "2022", ""),
         ("2022-25", "2022", "2026", ""), ("2026", "2026", "2027", "26"))


def v1(data):
    print("=== V1 VIX divergence (first per day)")
    br = ML.index(30)
    for lab, lo, hi, suf in ERAS4:
        rows = sorted((r for r in parse_mf(f"{data}/MFEAT{suf}_tags.txt") if lo <= r["date"] < hi), key=lambda r: (r["date"], r["hm"]))
        seen, eod, brk = set(), [], []
        for r in rows:
            if r["date"] in seen:
                continue
            d = -1 if (r["ret"] > 0.003 and r["vixchg"] > 0) else (1 if (r["ret"] < -0.003 and r["vixchg"] < 0) else 0)
            if d == 0:
                continue
            seen.add(r["date"])
            eod.append((r["date"], d * r["eod"] / r["e"] * 1e4))
            brk.append((r["date"], bp(r, d, br, br)))
        print(f"   {lab:<8} n {len(eod):4d} | to 15:55 {B.stat(eod)} | +/-0.30% {B.stat(brk)}")


def s1(data):
    L.NAMES = ("BARS5A", "BARS5B")
    nq = {d["date"]: d["bars"] for d in L.load(data)}
    L.NAMES = ("BARS5ESA", "BARS5ESB")
    es = {d["date"]: d["bars"] for d in L.load(data)}
    ev = {"S1 ES new extreme, NQ not -> fade NQ": [], "S2 NQ new extreme, ES not -> follow NQ": []}
    for d in sorted(set(nq) & set(es)):
        a, b = nq[d], es[d]
        nh, nl = max(x[1] for x in a[:6]), min(x[2] for x in a[:6])
        eh, el = max(x[1] for x in b[:6]), min(x[2] for x in b[:6])
        got = set()
        for k in range(6, B.K1 + 1):
            n_hi, n_lo = a[k][1] > nh, a[k][2] < nl
            e_hi, e_lo = b[k][1] > eh, b[k][2] < el
            if "S1" not in got:
                if e_hi and not n_hi:
                    ev["S1 ES new extreme, NQ not -> fade NQ"].append((d, k, -1, a)); got.add("S1")
                elif e_lo and not n_lo:
                    ev["S1 ES new extreme, NQ not -> fade NQ"].append((d, k, 1, a)); got.add("S1")
            if "S2" not in got:
                if n_hi and not e_hi:
                    ev["S2 NQ new extreme, ES not -> follow NQ"].append((d, k, 1, a)); got.add("S2")
                elif n_lo and not e_lo:
                    ev["S2 NQ new extreme, ES not -> follow NQ"].append((d, k, -1, a)); got.add("S2")
            nh, nl = max(nh, a[k][1]), min(nl, a[k][2])
            eh, el = max(eh, b[k][1]), min(el, b[k][2])
    for name, evs in ev.items():
        print(f"=== {name}")
        for lab, lo, hi in (("2018-21", "2018", "2022"), ("2022-25", "2022", "2026")):
            sel = [e for e in evs if lo <= e[0] < hi]
            cells = [f"{h}: {B.stat([(d, B.fwd(b, k, dd, n)) for d, k, dd, b in sel])}" for h, n in B.HOR]
            print(f"   {lab} n {len(sel):4d} | " + " | ".join(cells))


def main():
    data = sys.argv[1]
    v1(data)
    s1(data)


if __name__ == "__main__":
    main()
