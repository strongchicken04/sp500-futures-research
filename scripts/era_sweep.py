"""All panel rules of the day (level_lab, ict_lab, simple_lab NR4) in four eras,
gross bp per trade (no costs), so 2010-17 can be compared with 2018-25.
Flags rules positive in all four eras. Exploratory: anything flagged is a
signal to re-test, not a result.
Usage: era_sweep.py DATA_DIR
"""
from __future__ import annotations

import math
import statistics as st
import sys

sys.path.insert(0, "scripts")
import level_lab as L  # noqa: E402
import ict_lab as I  # noqa: E402
from mc_simple import nr4  # noqa: E402

ERAS = (("2010-13", "2010", "2014"), ("2014-17", "2014", "2018"), ("2018-21", "2018", "2022"), ("2022-25", "2022", "2026"))


def main():
    data = sys.argv[1]
    L.COST, L.STOP_COST = 0.0, 0.0
    def load(names):
        L.NAMES = names
        ds = L.load(data)
        import ict_lab
        extra = {}
        for nm in names:
            for raw in open(f"{data}/{nm}_tags.txt"):
                f = raw.strip().split(",")
                if f[0] == "H" and len(f) >= 16:
                    extra[f[1]] = tuple(float(x) for x in f[12:16])
        for d in ds:
            d["ah"], d["al"], d["lh"], d["ll"] = extra.get(d["date"].replace("-", ""), (0, 0, 0, 0))
        return ds
    days = load(("B2_0A", "B2_0B")) + load(("B2A", "B2B"))
    L.annotate(days)
    L.annotate_volume(days)
    R = dict(L.rules())
    R.update({k: v for k, v in I.rules().items() if not k.startswith("PW")})
    R["NR4"] = nr4(days)
    price = {d["date"]: d["bars"][0][0] for d in days}
    flagged = []
    for name, fn in R.items():
        ts = L.trades(days, fn)
        cells, means = [], []
        for lab, lo, hi in ERAS:
            v = [t["pts"] / price[t["date"]] * 1e4 for t in ts if lo <= t["date"] < hi]
            if len(v) < 5:
                cells.append(f"{lab} n{len(v)}")
                means.append(0)
                continue
            m = st.mean(v)
            means.append(m)
            cells.append(f"{lab} {m:+5.1f} t{m / st.pstdev(v) * math.sqrt(len(v)):+4.1f}")
        mark = "  <== all four positive" if all(m > 0 for m in means) else ""
        if mark:
            flagged.append(name)
        print(f"{name:<18} " + " | ".join(cells) + mark)
    print("\nall four eras positive (gross):", ", ".join(flagged) or "none")


if __name__ == "__main__":
    main()
