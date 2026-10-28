"""Sprints on FOMC days (owner question 2026-10-28): 09:31 eval sprint (Lucid
7: 50-day trend bias, +0.20 / -0.40), RS sprint (Lucid 8: first RS signal of
10:00 / 11:00 / 13:00 / 14:30, +0.20 / -0.30) and VWAP sprint (Lucid 12: side
of VWAP at 10:00, +0.25 / -0.40), flat 15:55. FOMC statement days 2018-2025
(63 meetings, list from news_fade_exporter.py) vs all other days, gross bp per
trade, resolved win rate (target or stop hit) vs the random-walk rate
S / (T + S), share of trades still open at the close (EOD).
Usage: fomc_sprints.py DATA_DIR
"""
from __future__ import annotations

import math
import re
import statistics as st
import sys

sys.path.insert(0, "scripts")
import two_win_sprint as W  # noqa: E402
from b_sprint_lab import trend_map, sgn  # noqa: E402
from score_cond_bracket import parse, LEVELS as CL  # noqa: E402
from score_multi_feature import parse as parse_mf, first_signals, LEVELS as ML  # noqa: E402

src = open("strategy/quantconnect/news_fade_exporter.py").read()
FOMC = {f"{d[:4]}-{d[4:6]}-{d[6:]}" for d in re.search(r'FOMC = set\("""(.*?)"""', src, re.S).group(1).split()}


def stats(rows, tp, sp):
    bp = [x[0] / x.e * 1e4 for x in rows]
    win = sum(1 for x in rows if x[0] >= x[1] - 1e-9)
    loss = sum(1 for x in rows if x[0] <= -x[2] - 0.2)
    t = st.mean(bp) / (st.pstdev(bp) / math.sqrt(len(bp))) if len(bp) > 2 and st.pstdev(bp) else 0.0
    return (f"n {len(rows):4d}  win {win / max(1, win + loss) * 100:5.1f}% of resolved (random {sp / (tp + sp) * 100:.0f}%)  "
            f"mean {st.mean(bp):+6.1f} bp (t {t:+4.1f})  open at close {(len(rows) - win - loss) / len(rows) * 100:4.1f}%")


def main():
    data = sys.argv[1]
    R = {}
    for r in parse([f"{data}/CBA_tags.txt"]):
        R.setdefault(r["type"], []).append(r)
    tm = trend_map(R["T931"])
    rs = first_signals(parse_mf(f"{data}/MFEAT_tags.txt"), lambda r: 1 if (r["rs"] > 0.0015 and r["vwapd"] > 0) else
                       (-1 if (r["rs"] < -0.0015 and r["vwapd"] < 0) else 0))
    S = {"09:31 eval sprint (Lucid 7)": ({r["date"]: (r, tm[r["date"]]) for r in R["T931"] if tm.get(r["date"])}, CL, 20, 40),
         "RS sprint (Lucid 8)": (rs, ML, 20, 30),
         "VWAP sprint 10:00 (Lucid 12)": ({r["date"]: (r, sgn(r["e"] - r["vwap"])) for r in R["T1000"] if sgn(r["e"] - r["vwap"])}, CL, 25, 40)}
    print(f"FOMC days in the list: {len(FOMC)} ({min(FOMC)} .. {max(FOMC)}); comparison 2018-2025")
    for name, (sig, lv, tp, sp) in S.items():
        f, o = [], []
        for d, (r, s) in sig.items():
            if not ("2018" <= d < "2026"):
                continue
            (f if d in FOMC else o).append(W.trade_pts(r, s, lv, tp, sp))
        print(f"--- {name}  +{tp / 100:.2f} / -{sp / 100:.2f}")
        print(f"   FOMC days   {stats(f, tp, sp)}")
        print(f"   other days  {stats(o, tp, sp)}")
    hm = {}
    for d, (r, s) in rs.items():
        if d in FOMC and "2018" <= d < "2026":
            hm[r["hm"]] = hm.get(r["hm"], 0) + 1
    print("RS signal time on FOMC days:", {f"{k // 60:02d}:{k % 60:02d}": v for k, v in sorted(hm.items())})


if __name__ == "__main__":
    main()
