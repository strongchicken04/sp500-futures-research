"""RS sprint with a 14:30 fallback on days without an RS signal (pre-specified):
if no RS signal by 14:30, at 14:30 go with the day (long if above the open and
above VWAP, short if below both), same sprint bracket. Also the fallback with
the 0.30% stop shape. Expected trading days to a pass and fees vs RS alone.

Usage: rs_fallback.py SCRATCH_DIR
"""
from __future__ import annotations

import statistics as st
import sys

sys.path.insert(0, "scripts")
from prop_sim import Trade  # noqa: E402
from mixed_accounts import calendar_days  # noqa: E402
from final_lifecycle import flat  # noqa: E402
from ladder_sim import outcomes  # noqa: E402
from score_multi_feature import parse, first_signals, LEVELS  # noqa: E402
from rs_sprint_shape import usd  # noqa: E402


def run(sig, cal, ti, si):
    res = []
    for lo, hi in (("0", "2022"), ("2022", "9")):
        trs = [Trade(d, usd(r, s, ti, si), "S") for d, (r, s) in sig.items() if lo <= d < hi]
        cc = [c for c in cal if lo <= c < hi]
        o = outcomes(calendar_days(trs, cc), flat(1, 1e6), window=200, start_pnl=0.0, target=3000.0, consistency=True)
        p = sum(1 for x, _ in o if x == "pass") / len(o)
        res.append(f"pass {p * 100:4.1f}%  days {st.mean(d for _, d in o) / p:5.1f}  fees ${90 / p:3.0f}  n/yr {len(trs) / 4:3.0f}")
    return " | ".join(res)


def main():
    rows = parse(f"{sys.argv[1]}/MFEAT_tags.txt")
    cal = sorted({r["date"] for r in rows})
    rs = first_signals(rows, lambda r: 1 if (r["rs"] > 0.0015 and r["vwapd"] > 0) else
                       (-1 if (r["rs"] < -0.0015 and r["vwapd"] < 0) else 0))
    fb = {}
    for r in rows:
        if r["hm"] == 870 and r["date"] not in rs:
            s = 1 if (r["ret"] > 0 and r["vwapd"] > 0) else (-1 if (r["ret"] < 0 and r["vwapd"] < 0) else 0)
            if s:
                fb[r["date"]] = (r, s)
    both = dict(rs, **fb)
    for tb, sb in ((20, 40), (20, 30)):
        ti, si = LEVELS.index(tb), LEVELS.index(sb)
        print(f"--- target {tb} / stop {sb} bp   (2018-21 | 2022-25)")
        print(f"   RS alone          {run(rs, cal, ti, si)}")
        print(f"   RS + 14:30 day    {run(both, cal, ti, si)}")
        print(f"   14:30 alone       {run(fb, cal, ti, si)}")


if __name__ == "__main__":
    main()
