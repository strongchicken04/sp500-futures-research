"""Do NR4 30-min breakouts or gap-and-go (gap >= 0.5%) add to the candidate book
(VG + Z without gate + RS, flat 3)? Paired bootstrap, vol gate on the new legs.
Usage: mc_simple.py DATA_DIR
"""
from __future__ import annotations

import sys

sys.path.insert(0, "scripts")
import level_lab as L  # noqa: E402
import simple_lab as S  # noqa: E402
import gate_check as G  # noqa: E402
from mc_book import compare, summary  # noqa: E402
from mc_runs import sized  # noqa: E402
from rescore_all import rvol  # noqa: E402


def nr4(days):
    for n, d in enumerate(days):
        rng = [days[j]["hi"] - days[j]["lo"] for j in range(max(0, n - 4), n)]
        d["nr4"] = n >= 4 and rng[-1] == min(rng)

    def fn(d, p):
        if not d["nr4"]:
            return None
        b = d["bars"]
        h, lo = max(x[1] for x in b[:6]), min(x[2] for x in b[:6])
        for i in range(6, L.LAST_ENTRY + 1):
            c = b[i][3]
            if c > h or c < lo:
                s = 1 if c > h else -1
                return s, L.run(b, i, s, c, lo if s == 1 else h)
        return None
    return fn


def main():
    data = sys.argv[1]
    base = [t for t in G.build(data, {"Z"}) if t[4] in ("VG", "Z", "RS")]
    days = L.load(data)
    reg = rvol()
    new = []
    for leg, fn in (("NR", nr4(days)), ("GG", S.gapgo)):
        new += [(t["date"], t["ehm"], t["xhm"], t["pts"] * 2.0, leg) for t in L.trades(days, fn) if reg.get(t["date"], 9.0) < 0.30]
    cand = {"VG": 3, "Z": 3, "RS": 3}
    tr = base + new
    cal_all = sorted({t[0] for t in tr})
    for lo, hi in (("0", "2022"), ("2022", "9")):
        cal = [d for d in cal_all if lo <= d < hi]
        V = {"VG+Zfree+RS": sized(tr, cand), "+ NR4 3": sized(tr, dict(cand, NR=3)), "+ NR4 1": sized(tr, dict(cand, NR=1)),
             "+ gap-and-go 3": sized(tr, dict(cand, GG=3)), "+ gap-and-go 1": sized(tr, dict(cand, GG=1))}
        print(f"--- {'2018-2021' if lo == '0' else '2022-2025'}")
        for line in summary(compare(V, cal, trials=3000, seed=53), "VG+Zfree+RS"):
            print("   " + line)


if __name__ == "__main__":
    main()
