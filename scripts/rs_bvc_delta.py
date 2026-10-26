"""RS signal x ESTIMATED order flow (bulk volume classification on 5-min bars),
to check the in-QC finding (real delta AGREE subset strong in 2019-26) in the
eras QC cannot cover (2010-17). Day shift 2026-10-26.
D = sum(volume x (2 x buy share - 1)) / sum(volume) from 09:30 to the check
(5-min bars, buy share as big_trades.py). x = D x signal direction.
AGREE = x at or above the 93rd percentile of x in 2018-21 (the real agree
group was ~7% of signals); AGAINST = x at or below the 7th percentile.
Step 1 (proxy validity): 2019-26 should repeat the real-data pattern.
Step 2: 2010-13 / 2014-17. Funded leg +/-1.25% gross bp and sprint 0.20/0.30
resolved win by group.
Usage: rs_bvc_delta.py DATA_DIR
"""
from __future__ import annotations

import math
import statistics as st
import sys

sys.path.insert(0, "scripts")
import big_trades as B  # noqa: E402
from score_multi_feature import parse as parse_mf, first_signals, LEVELS as ML, bp  # noqa: E402

KEND = {600: 5, 660: 17, 780: 41, 870: 59}
ERAS = (("2010-13", "2010", "2014"), ("2014-17", "2014", "2018"), ("2018-21", "2018", "2022"),
        ("2022-25", "2022", "2026"), ("2026", "2026", "2027"), ("2019-26", "2019", "2027"))


def main():
    data = sys.argv[1]
    days = B.load(data)
    idx = {d: i for i, (d, _) in enumerate(days)}
    sig = {}
    for suf in ("_OLD", "", "26"):
        sig.update(first_signals(parse_mf(f"{data}/MFEAT{suf}_tags.txt"), lambda r: 1 if (r["rs"] > 0.0015 and r["vwapd"] > 0) else
                                 (-1 if (r["rs"] < -0.0015 and r["vwapd"] < 0) else 0)))
    rows = []
    for d, (r, s) in sig.items():
        i = idx.get(d)
        if i is None or i < 20 or r["hm"] not in KEND:
            continue
        b = days[i][1]
        rets = [p[k][3] / p[k - 1][3] - 1 for _, p in days[i - 20:i] for k in range(1, 78)]
        sd = st.pstdev(rets)
        k = KEND[r["hm"]]
        num = den = 0.0
        for j in range(1, k + 1):
            sh = B.phi((b[j][3] / b[j - 1][3] - 1) / sd)
            num += b[j][4] * (2 * sh - 1)
            den += b[j][4]
        if den > 0:
            rows.append((d, s * num / den, r, s))
    tune = sorted(x for d, x, _, _ in rows if "2018" <= d < "2022")
    hi_cut, lo_cut = tune[int(0.93 * len(tune))], tune[int(0.07 * len(tune))]
    print(f"cuts from 2018-21: agree >= {hi_cut:+.3f}, against <= {lo_cut:+.3f}")
    big, ti, si = ML.index(125), ML.index(20), ML.index(30)
    for lab, lo, hi in ERAS:
        cells = []
        for name, f in (("AGREE", lambda x: x >= hi_cut), ("neutral", lambda x: lo_cut < x < hi_cut), ("AGAINST", lambda x: x <= lo_cut)):
            g = [(r, s) for d, x, r, s in rows if lo <= d < hi and f(x)]
            if len(g) < 5:
                cells.append(f"{name} n<5")
                continue
            leg = [bp(r, s, big, big) for r, s in g]
            sp = [bp(r, s, ti, si) for r, s in g]
            h, m = sum(v == 20 for v in sp), sum(v == -30 for v in sp)
            t = st.mean(leg) / (st.pstdev(leg) / math.sqrt(len(leg))) if st.pstdev(leg) else 0
            cells.append(f"{name} leg {st.mean(leg):+5.1f} (t{t:+4.1f}) win {h / max(1, h + m) * 100:3.0f}% n{len(g)}")
        print(f"{lab:<8} " + " | ".join(cells))


if __name__ == "__main__":
    main()
