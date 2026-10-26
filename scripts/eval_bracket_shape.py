"""Evaluation bracket SHAPE under the intraday drawdown (day shift 2026-10-26,
fixed before results). With the intraday rule a full loss (~$1,950) leaves
~$50 and kills the evaluation. A bracket with target >= stop is sized by the
$1,450 win cap, so its loss is smaller (0.30/0.20: ~$970) and a second trade
still fits the room. Does that pass faster / cheaper?

RS sprint (first signal of 10:00 / 11:00 / 13:00 / 14:30), two-win sizing of
two_win_sprint (INTRA: every trade fits the room - $50, dead account -> new
evaluation). Brackets (bp target / stop): plan 20/30 and 25/40; candidates
30/20, 25/25, 30/30, 40/30, 50/40. Four eras + 2026 holdout: days and fees to
a pass from every start day, pass rate per evaluation, random direction
(10 seeds) as the ceiling check (<= 40%). Adopt only if faster AND cheaper
than 20/30 in all four eras and in 2026.
Usage: eval_bracket_shape.py DATA_DIR
"""
from __future__ import annotations

import random
import statistics as st
import sys

sys.path.insert(0, "scripts")
from score_multi_feature import parse as parse_mf, first_signals, LEVELS as ML  # noqa: E402
from score_cond_bracket import parse  # noqa: E402
from two_win_sprint import trade_pts, attempt_days, FEE  # noqa: E402

BR = [(20, 30), (25, 40), (30, 20), (25, 25), (30, 30), (40, 30), (50, 40)]
ERAS = (("2010-13", "2010", "2014", "_OLD", 260), ("2014-17", "2014", "2018", "_OLD", 260),
        ("2018-21", "2018", "2022", "", 260), ("2022-25", "2022", "2026", "", 260), ("2026", "2026", "2027", "26", 40))


def run(sig, cal, tp, sp, left, flip=None):
    days = [trade_pts(sig[d][0], (flip or {}).get(d, sig[d][1]), ML, tp, sp) if d in sig else None for d in cal]
    res = [x for x in (attempt_days(days, s0, "two-win") for s0 in range(len(days) - left)) if x]
    return st.mean(d for d, _ in res), st.mean(e for _, e in res) * FEE, len(res) / sum(e for _, e in res)


def main():
    data = sys.argv[1]
    for lab, lo, hi, suf, left in ERAS:
        rs = {d: v for d, v in first_signals(parse_mf(f"{data}/MFEAT{suf}_tags.txt"), lambda r: 1 if (r["rs"] > 0.0015 and r["vwapd"] > 0) else
                                             (-1 if (r["rs"] < -0.0015 and r["vwapd"] < 0) else 0)).items() if lo <= d < hi}
        cal = sorted(d for d in {r["date"] for r in parse([f"{data}/CBA{suf}_tags.txt"]) if r["type"] == "T931"} if lo <= d < hi)
        print(f"--- {lab}: days / fees to a pass | pass per evaluation | random direction (10 seeds)")
        for tp, sp in BR:
            d, f, p = run(rs, cal, tp, sp, left)
            rnd = []
            for seed in range(10):
                g = random.Random(seed)
                rnd.append(run(rs, cal, tp, sp, left, {x: g.choice((1, -1)) for x in rs})[2])
            print(f"   +{tp / 100:.2f}/-{sp / 100:.2f}  {d:5.1f} d  ${f:4.0f}  pass {p * 100:4.1f}%  random {st.mean(rnd) * 100:4.1f}%")


if __name__ == "__main__":
    main()
