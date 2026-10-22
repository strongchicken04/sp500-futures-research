"""Noise-area momentum variants (queue item 7), pre-specified:
  a) profit target only (exit at +TP bp if reached before the trailing exit)
  b) hard stop only (exit at -SL bp if reached first)
  c) both, as a block average (no single cell picked)
  d) half off at TP, rest rides the published exit ("partial target")
NQ points per trade, cost 0.5 pt per MNQ round trip as in score_noise_tod.

Usage: noise_variants.py SCRATCH_DIR
"""
from __future__ import annotations

import statistics as st
import sys

sys.path.insert(0, "scripts")
from score_noise_tod import parse, z_result, tstat, COST_PTS  # noqa: E402


def row(lab, fn, Z):
    a = [fn(z) for z in Z if z["ymd"] < "2022"]
    b = [fn(z) for z in Z if z["ymd"] >= "2022"]
    wr = lambda v: sum(x > 0 for x in v) / len(v) * 100
    print(f"  {lab:<28} IS {st.mean(a):+6.2f} t{tstat(a):+4.1f} WR {wr(a):3.0f}% | OOS {st.mean(b):+6.2f} t{tstat(b):+4.1f} WR {wr(b):3.0f}%")


def main():
    Z, _ = parse(f"{sys.argv[1]}/NOISETOD_tags.txt")
    row("published", lambda z: z_result(z), Z)
    for tp in (20, 30, 50, 75, 100):
        row(f"TP {tp} bp", lambda z, tp=tp: z_result(z, tp), Z)
    for sl in (20, 30, 50, 75):
        row(f"SL {sl} bp", lambda z, sl=sl: z_result(z, None, sl), Z)
    cells = [(tp, sl) for tp in (30, 40, 50, 60, 75) for sl in (30, 40, 50, 60, 75)]
    row("TP 30-75 x SL 30-75 block", lambda z: st.mean(z_result(z, tp, sl) for tp, sl in cells), Z)
    for tp in (30, 50, 75):
        row(f"half off at TP {tp}", lambda z, tp=tp: 0.5 * z_result(z, tp) + 0.5 * z_result(z), Z)


if __name__ == "__main__":
    main()
