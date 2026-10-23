"""Two-account plan (RS 0.20/0.30 on A, 09:31 trend 0.25/0.40 on B, hedge guard
on A) with today's sizing vs the two-win sizing + exact finisher
(two_win_sprint.py), four eras: days and fees to the first funded account.
Usage: two_win_pair.py DATA_DIR
"""
from __future__ import annotations

import statistics as st
import sys

sys.path.insert(0, "scripts")
from score_multi_feature import parse as parse_mf, first_signals, LEVELS as ML  # noqa: E402
from score_cond_bracket import parse, LEVELS as CL  # noqa: E402
from b_sprint_lab import trend_map  # noqa: E402
from hedge_check import exit_min  # noqa: E402
from two_win_sprint import ERAS, FEE, trade_pts, attempt_days  # noqa: E402


def series(sig, cal, lv, tp, sp, skip=()):
    out = []
    for d in cal:
        if d in sig and d not in skip:
            r, s = sig[d]
            out.append(trade_pts(r, s, lv, tp, sp))
        else:
            out.append(None)
    return out


def main():
    data = sys.argv[1]
    for lab, lo, hi, suf in ERAS:
        rs = {d: v for d, v in first_signals(parse_mf(f"{data}/MFEAT{suf}_tags.txt"), lambda r: 1 if (r["rs"] > 0.0015 and r["vwapd"] > 0) else
                                             (-1 if (r["rs"] < -0.0015 and r["vwapd"] < 0) else 0)).items() if lo <= d < hi}
        R = {}
        for r in parse([f"{data}/CBA{suf}_tags.txt"]):
            R.setdefault(r["type"], []).append(r)
        tm = trend_map(R["T931"])
        t9 = {r["date"]: (r, tm[r["date"]]) for r in R["T931"] if lo <= r["date"] < hi and tm.get(r["date"])}
        skip = set()
        for d, (ra, sa) in rs.items():
            if d in t9 and t9[d][1] != sa:
                rb, sb = t9[d]
                fav, adv = (rb["up"], rb["dn"]) if sb == 1 else (rb["dn"], rb["up"])
                if ra["hm"] < exit_min(571, fav, adv, CL.index(25), CL.index(40)):
                    skip.add(d)
        cal = sorted(set(rs) | set(t9))
        A = series(rs, cal, ML, 20, 30, skip)
        B = series(t9, cal, CL, 25, 40)
        out = []
        for pol in ("now", "two-win"):
            res = []
            for s0 in range(len(cal) - 260):
                a = attempt_days(A, s0, pol)
                b = attempt_days(B, s0, pol)
                if not a or not b:
                    continue
                first = min(a[0], b[0])
                ea = a[1] if a[0] == first else None
                res.append((first, (a[1] if a[0] <= first else 1 + a[1] * first // max(1, a[0])) + (b[1] if b[0] <= first else 1 + b[1] * first // max(1, b[0]))))
            out.append(f"{pol}: {st.mean(x for x, _ in res):5.1f} d ~${st.mean(y for _, y in res) * FEE:4.0f}")
        print(f"{lab}: first funded, RS + 09:31 with hedge guard -> " + " | ".join(out))


if __name__ == "__main__":
    main()
