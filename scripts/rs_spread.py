"""Does the RS edge live in NQ's direction or in the NQ-ES SPREAD? (day shift
2026-10-26, fixed before results). On each RS signal (first of 10:00 / 11:00 /
13:00 / 14:30) measure from the close of the 5-min bar at the check to 15:55:
  NQ    signal direction x NQ return (what the leg trades, no bracket)
  ES    signal direction x ES return
  SPR   NQ - ES (long NQ / short ES on a long signal), the market-neutral part
  SPRb  NQ - 1.25 x ES (beta-neutral-ish; 1.25 fixed before results)
Gross bp, t, correlation of SPR with NQ by trade. First run 2018-25 only;
four eras + 2026 once the ES panels B2ES_0A / B2ES_0B / B2ES_26 exist
(strategy/quantconnect/es_bars, run 2026-10-26).
Usage: rs_spread.py DATA_DIR
"""
from __future__ import annotations

import math
import statistics as st
import sys

sys.path.insert(0, "scripts")
import level_lab as L  # noqa: E402
from score_multi_feature import parse as parse_mf, first_signals  # noqa: E402

K = {600: 5, 660: 17, 780: 41, 870: 59}


def tstat(v):
    return st.mean(v) / (st.pstdev(v) / math.sqrt(len(v))) if len(v) > 2 and st.pstdev(v) else 0.0


def main():
    data = sys.argv[1]
    nq, es = {}, {}
    for names, tgt in ((("B2_0A", "B2_0B"), nq), (("BARS5A", "BARS5B"), nq), (("B2_26",), nq),
                       (("B2ES_0A", "B2ES_0B"), es), (("BARS5ESA", "BARS5ESB"), es), (("B2ES_26",), es)):
        L.NAMES = names
        tgt.update({d["date"]: d["bars"] for d in L.load(data)})
    sig = {}
    for suf in ("_OLD", "", "26"):
        sig.update(first_signals(parse_mf(f"{data}/MFEAT{suf}_tags.txt"), lambda r: 1 if (r["rs"] > 0.0015 and r["vwapd"] > 0) else
                                 (-1 if (r["rs"] < -0.0015 and r["vwapd"] < 0) else 0)))
    for lab, lo, hi in (("2010-13", "2010", "2014"), ("2014-17", "2014", "2018"), ("2018-21", "2018", "2022"),
                        ("2022-25", "2022", "2026"), ("2026", "2026", "2027")):
        a, b = [], []
        for d, (r, s) in sorted(sig.items()):
            if not (lo <= d < hi) or d not in nq or d not in es or r["hm"] not in K:
                continue
            k = K[r["hm"]]
            n0, n1 = nq[d][k][3], nq[d][L.EOD][3]
            e0, e1 = es[d][k][3], es[d][L.EOD][3]
            a.append(s * (n1 / n0 - 1) * 1e4)
            b.append(s * (e1 / e0 - 1) * 1e4)
        if len(a) < 10:
            print(f"--- {lab}: no ES panel yet")
            continue
        spr = [x - y for x, y in zip(a, b)]
        sprb = [x - 1.25 * y for x, y in zip(a, b)]
        mx, ms = st.mean(a), st.mean(spr)
        cov = sum((x - mx) * (y - ms) for x, y in zip(a, spr)) / len(a)
        corr = cov / (st.pstdev(a) * st.pstdev(spr))
        print(f"--- {lab} (n {len(a)}): NQ {st.mean(a):+5.1f} bp (t{tstat(a):+4.1f}) | ES {st.mean(b):+5.1f} bp (t{tstat(b):+4.1f}) | "
              f"SPREAD {ms:+5.1f} bp (t{tstat(spr):+4.1f}, sd {st.pstdev(spr):4.1f} vs NQ sd {st.pstdev(a):4.1f}) | corr(SPR, NQ) {corr:+.2f} | "
              f"SPRb {st.mean(sprb):+5.1f} bp (t{tstat(sprb):+4.1f}, sd {st.pstdev(sprb):4.1f})")


if __name__ == "__main__":
    main()
