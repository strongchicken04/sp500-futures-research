"""Timing robustness of the RS signal (night 2026-10-24/25, guardrail 6c):
checks at 10:00 / 11:00 / 13:00 / 14:30 (live) vs all shifted -5 min and
+5 min (exports MFEAT*_M5 / *_P5). Per era: RS funded leg (+/-1.25%, vol
gate) $ per MNQ trade at today's NQ (net) and the RS sprint (0.20 / 0.30%)
resolved win rate vs random 60%.
Usage: rs_timing.py DATA_DIR
"""
from __future__ import annotations

import math
import statistics as st
import sys

sys.path.insert(0, "scripts")
from score_multi_feature import parse as parse_mf, first_signals, LEVELS  # noqa: E402
from rs_book import pts as rs_pts  # noqa: E402
from rescore_all import rvol  # noqa: E402
from size_today import PRICE, rvmap  # noqa: E402

ERAS = (("_OLD", "2010", "2014", "2010-13"), ("_OLD", "2014", "2018", "2014-17"), ("", "2018", "2022", "2018-21"), ("", "2022", "2026", "2022-25"))


def main():
    data = sys.argv[1]
    reg = rvol()
    ro = rvmap(data, ("LSVWAP_OLD", "LSNOISE_OLD"))
    rule = lambda r: 1 if (r["rs"] > 0.0015 and r["vwapd"] > 0) else (-1 if (r["rs"] < -0.0015 and r["vwapd"] < 0) else 0)
    ti = si = LEVELS.index(125)
    t2, s3 = LEVELS.index(20), LEVELS.index(30)
    print(f"RS timing: funded leg $ per MNQ trade at NQ {PRICE:,.0f} (t) | sprint 0.20/0.30 resolved win (random 60%)")
    for shift in ("_M5", "", "_P5"):
        cells = []
        for suf, lo, hi, lab in ERAS:
            gate = (lambda d: 0 < ro.get(d, 9.0) < 0.30) if suf else (lambda d: reg.get(d, 9.0) < 0.30)
            sig = {d: v for d, v in first_signals(parse_mf(f"{data}/MFEAT{suf}{shift}_tags.txt"), rule).items() if lo <= d < hi}
            v = []
            h = l_ = 0
            for d, (r, s) in sig.items():
                fav, adv = (r["up"], r["dn"]) if s == 1 else (r["dn"], r["up"])
                if fav[t2] >= 0 and (adv[s3] < 0 or fav[t2] < adv[s3]):
                    h += 1
                elif adv[s3] >= 0:
                    l_ += 1
                if not gate(d):
                    continue
                p = rs_pts(r, s, ti, si)
                c = 1.0 if p < -0.0124 * r["e"] else 0.75
                v.append(((p + c) / r["e"] * PRICE - c) * 2.0)
            cells.append(f"{lab} ${st.mean(v):+6.1f} (t{st.mean(v) / st.pstdev(v) * math.sqrt(len(v)):+3.1f}) {h / (h + l_) * 100:4.1f}%")
        print(f"   {shift or 'live':<5} " + " | ".join(cells))


if __name__ == "__main__":
    main()
