"""Noise momentum (Lucid 6 live rules, 0.50% hard stop = NS) on gold and crude
for funded-book diversification (day shift 2026-10-23). Dollars per micro
(MGC $10/pt, tick 0.1; MCL $100/pt, tick 0.01) net of $1 + 1 tick (+1 on
stops); vol gate on the market's own 20d realised vol < 0.30 and gate off.
Then the daily correlation with NQ noise.
Usage: xm_noise.py SCRATCH_DIR
"""
from __future__ import annotations

import statistics as st
import sys
from collections import defaultdict

sys.path.insert(0, "scripts")
from noise_markets import load, stat  # noqa: E402

SPEC = {"NQ": ("LSNOISE", 2.0, 0.25), "GC": ("LSNOISE_GC", 10.0, 0.1), "CL": ("LSNOISE_CL", 100.0, 0.01)}


def main():
    sp = sys.argv[1]
    daily = {}
    for m, (f, mult, tick) in SPEC.items():
        T = load(f"{sp}/{f}_tags.txt", mult, tick)
        for gate in (True, False):
            g = [(d, u) for d, u, rv in T["NS"] if not gate or 0 < rv < 0.30]
            a = [u for d, u in g if d < "2022"]
            b = [u for d, u in g if d >= "2022"]
            yrs = sorted({d[:4] for d, _ in g})
            by = " ".join(f"{y[2:]}:{sum(u for d, u in g if d[:4] == y):+.0f}" for y in yrs)
            print(f"{m} NS gate {'on ' if gate else 'off'}: 2018-21 {stat(a)} | 2022-25 {stat(b)}   {by}")
            if gate:
                dd = defaultdict(float)
                for d, u in g:
                    dd[d] += u
                daily[m] = dd
    for m in ("GC", "CL"):
        common = sorted(set(daily["NQ"]) | set(daily[m]))
        print(f"daily corr NQ-{m}: {st.correlation([daily['NQ'].get(d, 0) for d in common], [daily[m].get(d, 0) for d in common]):+.2f}")


if __name__ == "__main__":
    main()
