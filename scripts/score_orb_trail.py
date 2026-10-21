"""Score the ORB exit variants (orb_trail_exporter): trailing on the 5- or
1-minute 20-EMA or not at all, initial stop from the opening range or a fixed
distance, optional fixed target. Wednesday and the volatility gate are
applied as in the book. Each variant's daily NQ points become MNQ dollars
($2/pt, $1 per MNQ per trade) and the evaluation is simulated at a fixed size.

Usage: score_orb_trail.py SCRATCH_DIR [MNQ]
"""
from __future__ import annotations

import math
import statistics as st
import sys
from collections import defaultdict

sys.path.insert(0, "scripts")
sys.path.insert(0, "strategy/quantconnect")
from prop_sim import Trade  # noqa: E402
from rescore_all import rvol  # noqa: E402
from mixed_accounts import calendar_days  # noqa: E402
from final_lifecycle import flat  # noqa: E402
from ladder_sim import outcomes  # noqa: E402

src = open("strategy/quantconnect/orb_trail_exporter.py").read()
VARIANTS: list = []
exec(src.split("VARIANTS = []")[1].split("EOD =")[0])


def name(v):
    trail, sl0, tp = v
    s = "OR stop" if sl0 == "or" else f"SL {sl0:g}"
    return f"trail {trail:<2} {s:<8} TP {('-' if tp is None else f'{tp:g}'):<5}"


def main():
    sp = sys.argv[1]
    mnq = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    reg = rvol()
    pnl = defaultdict(lambda: [0.0] * len(VARIANTS))
    ntr = defaultdict(lambda: [0] * len(VARIANTS))
    for raw in open(f"{sp}/ORBTRAIL_tags.txt"):
        f = raw.strip().split(",")
        if f[0] != "T":
            continue
        d, j = f"{f[1][:4]}-{f[1][4:6]}-{f[1][6:]}", int(f[2])
        vals = f[3:]
        k = len(vals) // 2
        for i in range(k):
            pnl[d][j + i] = float(vals[i])
            ntr[d][j + i] = int(vals[k + i])
    import datetime as dt
    days = sorted(d for d in pnl if reg.get(d, 9.0) < 0.30
                  and dt.date.fromisoformat(d).weekday() != 2)
    cal = days
    print(f"{len(days)} trading days (Wednesday and high-volatility days skipped), size {mnq} MNQ\n")
    print(f"{'variant':<34} {'trades/d':>8} {'pts/d IS':>8} {'pts/d OOS':>9} {'win days':>8} "
          f"{'pass IS':>8} {'pass OOS':>9} {'days':>5}")
    rows = []
    for i, v in enumerate(VARIANTS):
        tr = [Trade(d, (pnl[d][i] * 2.0 - ntr[d][i] * 1.0) * mnq, "O") for d in days if ntr[d][i] > 0]
        a = [pnl[d][i] for d in days if d < "2022"]
        b = [pnl[d][i] for d in days if d >= "2022"]
        wd = [pnl[d][i] for d in days if ntr[d][i] > 0]
        res = []
        for lo, hi in (("0", "2022"), ("2022", "9")):
            o = outcomes(calendar_days([t for t in tr if lo <= t.date < hi], [c for c in cal if lo <= c < hi]),
                         flat(1, 1e6), window=250, start_pnl=0.0, target=3000.0, consistency=True)
            p = sum(1 for x, _ in o if x == "pass") / len(o) * 100
            md = sorted(dd for x, dd in o if x == "pass")
            res.append((p, md[len(md) // 2] if md else 0))
        rows.append((v, st.mean(ntr[d][i] for d in days), st.mean(a), st.mean(b),
                     sum(1 for x in wd if x > 0) / len(wd) * 100, res))
    for v, n, a, b, w, res in rows:
        flag = "  <- book" if v == ("5m", "or", None) else ""
        print(f"{name(v):<34} {n:8.2f} {a:+8.2f} {b:+9.2f} {w:7.0f}% {res[0][0]:7.1f}% {res[1][0]:8.1f}% {res[1][1]:5}{flag}")


if __name__ == "__main__":
    main()
