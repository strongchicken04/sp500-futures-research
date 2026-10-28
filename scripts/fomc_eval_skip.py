"""Evaluation with the RS sprint: trade FOMC days or skip them (night
2026-10-28/29, fixed before results; follows fomc_sprints.py where the RS
edge was ~random on FOMC days, n 51). 50K and 25K accounts as eval_25k.py
(INTRA, re-priced at NQ 28,530), bracket +0.20 / -0.30, 2018-21 and 2022-25
(FOMC list covers 2018-2025 only). Days and fees to a pass.
Usage: fomc_eval_skip.py DATA_DIR
"""
from __future__ import annotations

import sys

sys.path.insert(0, "scripts")
import eval_25k as E  # noqa: E402
from fomc_sprints import FOMC  # noqa: E402
from score_multi_feature import parse as parse_mf, first_signals  # noqa: E402


def main():
    data = sys.argv[1]
    mf = parse_mf(f"{data}/MFEAT_tags.txt")
    rs = first_signals(mf, lambda r: 1 if (r["rs"] > 0.0015 and r["vwapd"] > 0) else (-1 if (r["rs"] < -0.0015 and r["vwapd"] < 0) else 0))
    for lo, hi, lab in (("2018", "2022", "2018-21"), ("2022", "2026", "2022-25")):
        cal = sorted({r["date"] for r in mf if lo <= r["date"] < hi})
        print(f"--- {lab}: days to a pass | evaluations | fees")
        for name, keep in (("trade FOMC days", lambda d: True), ("skip FOMC days", lambda d: d not in FOMC)):
            sig = {d: E.scaled(r, s, 20, 30) for d, (r, s) in rs.items() if lo <= d < hi and keep(d)}
            cells = []
            for acc, a in E.ACC.items():
                dd, ev, p = E.run(sig, cal, a)
                cells.append(f"{acc}: {dd:5.1f} d  {ev:4.2f} eval  ${ev * a['fee']:4.0f}")
            print(f"   {name:<16} " + "   ".join(cells))


if __name__ == "__main__":
    main()
