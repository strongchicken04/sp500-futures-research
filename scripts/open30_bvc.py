"""F6 local proxy (day shift 2026-10-26): estimated aggressive imbalance of
09:30-10:00 (bulk volume classification on 5-min bars) -> trade its sign from
the 10:00 close to 12:00 and to 15:55. The in-QC real-data version (F6) gave
+33 / -1 / +21 bp to 15:55 in 2024 / 2023 / 2022 on |D| >= 5%. Here: top /
bottom 10% of D (cuts fixed on 2018-21) and the middle, four eras + 2026.
Usage: open30_bvc.py DATA_DIR
"""
from __future__ import annotations

import statistics as st
import sys

sys.path.insert(0, "scripts")
import big_trades as B  # noqa: E402
import level_lab as L  # noqa: E402


def main():
    days = B.load(sys.argv[1])
    rows = []
    for i in range(20, len(days)):
        d, b = days[i]
        rets = [p[k][3] / p[k - 1][3] - 1 for _, p in days[i - 20:i] for k in range(1, 78)]
        sd = st.pstdev(rets)
        num = den = 0.0
        for j in range(0, 6):
            ref = b[j - 1][3] if j else days[i - 1][1][L.EOD][3]
            sh = B.phi((b[j][3] / ref - 1) / sd)
            num += b[j][4] * (2 * sh - 1)
            den += b[j][4]
        if den > 0:
            rows.append((d, num / den, (b[29][3] / b[5][3] - 1) * 1e4, (b[L.EOD][3] / b[5][3] - 1) * 1e4))
    tune = sorted(x[1] for x in rows if "2018" <= x[0] < "2022")
    hi, lo = tune[int(0.9 * len(tune))], tune[int(0.1 * len(tune))]
    print(f"cuts (2018-21): top >= {hi:+.3f}, bottom <= {lo:+.3f}")
    for lab, a, c in B.ERAS:
        sel = [x for x in rows if a <= x[0] < c]
        ext = [x for x in sel if x[1] >= hi or x[1] <= lo]
        mid = [x for x in sel if lo < x[1] < hi]
        f = lambda g, k: B.stat([(x[0], x[k] * (1 if x[1] > 0 else -1)) for x in g])
        print(f"{lab:<8} extreme 10%+10% (n {len(ext):3d}): to 12:00 {f(ext, 2)} to 15:55 {f(ext, 3)} | middle: to 15:55 {f(mid, 3)}")


if __name__ == "__main__":
    main()
