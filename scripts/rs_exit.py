"""RS funded leg: exit rule variants (day shift 2026-10-26, fixed before
results). The leg (Lucid 8 funded mode) enters on the first RS signal
(10:00 / 11:00 / 13:00 / 14:30) with a +/-1.25% bracket and is mostly flat
at 15:55. Variants on the SAME trades (entry at the close of the 5-min bar
ending at the check, 5-min panels BARS5 / B2_0 / B2_26, fills as level_lab:
stop at min(stop, open), exits checked from the next bar):
  BASE  +/-1.25% bracket, else 15:55
  VWX   stop 1.25%; exit at the first 5-min close on the wrong side of the
        session VWAP (long: close < VWAP), else 15:55
  BE    +/-1.25% bracket; once the trade is +0.50% in favour (bar high / low),
        the stop moves to the entry
GROSS bp per trade (costs equal for all), t, and the paired difference vs BASE
by era 2010-13 / 2014-17 / 2018-21 / 2022-25 / 2026. Adopt only if better in
all four eras and not worse in 2026.
Usage: rs_exit.py DATA_DIR
"""
from __future__ import annotations

import math
import statistics as st
import sys

sys.path.insert(0, "scripts")
import level_lab as L  # noqa: E402
from score_multi_feature import parse as parse_mf, first_signals  # noqa: E402

ERAS = (("2010-13", "2010", "2014"), ("2014-17", "2014", "2018"), ("2018-21", "2018", "2022"),
        ("2022-25", "2022", "2026"), ("2026", "2026", "2027"))
K = {600: 5, 660: 17, 780: 41, 870: 59}


def sim(b, k, d, variant):
    e = b[k][3]
    stop, tgt = e * (1 - d * 0.0125), e * (1 + d * 0.0125)
    pv = sum((x[1] + x[2] + x[3]) / 3 * x[4] for x in b[:k + 1])
    vv = sum(x[4] for x in b[:k + 1])
    armed = False
    for j in range(k + 1, L.EOD + 1):
        o, h, lo, c, v = b[j]
        if (d == 1 and lo <= stop) or (d == -1 and h >= stop):
            x = min(stop, o) if d == 1 else max(stop, o)
            return d * (x - e) / e * 1e4
        if variant != "VWX" and ((d == 1 and h >= tgt) or (d == -1 and lo <= tgt)):
            return d * (tgt - e) / e * 1e4
        pv += (h + lo + c) / 3 * v
        vv += v
        if variant == "VWX" and vv > 0 and d * (c - pv / vv) < 0:
            return d * (c - e) / e * 1e4
        if variant == "BE" and not armed and ((d == 1 and h >= e * 1.005) or (d == -1 and lo <= e * 0.995)):
            armed, stop = True, e
    return d * (b[L.EOD][3] - e) / e * 1e4


def main():
    data = sys.argv[1]
    bars = {}
    for names in (("B2_0A", "B2_0B"), ("BARS5A", "BARS5B"), ("B2_26",)):
        L.NAMES = names
        for dd in L.load(data):
            bars[dd["date"]] = dd["bars"]
    sig = {}
    for suf in ("_OLD", "", "26"):
        sig.update(first_signals(parse_mf(f"{data}/MFEAT{suf}_tags.txt"), lambda r: 1 if (r["rs"] > 0.0015 and r["vwapd"] > 0) else
                                 (-1 if (r["rs"] < -0.0015 and r["vwapd"] < 0) else 0)))
    for lab, lo, hi in ERAS:
        tr = [(bars[d], K[r["hm"]], s) for d, (r, s) in sorted(sig.items()) if lo <= d < hi and d in bars and r["hm"] in K]
        base = [sim(b, k, s, "BASE") for b, k, s in tr]
        cells = [f"BASE {st.mean(base):+5.1f} bp (t{st.mean(base) / (st.pstdev(base) / math.sqrt(len(base))):+4.1f}, n{len(base)})"]
        for v in ("VWX", "BE"):
            x = [sim(b, k, s, v) for b, k, s in tr]
            dd = [a - c for a, c in zip(x, base)]
            td = st.mean(dd) / (st.pstdev(dd) / math.sqrt(len(dd))) if st.pstdev(dd) else 0
            cells.append(f"{v} {st.mean(x):+5.1f} bp (vs BASE {st.mean(dd):+5.1f}, t{td:+4.1f})")
        print(f"--- {lab}: " + " | ".join(cells))


if __name__ == "__main__":
    main()
