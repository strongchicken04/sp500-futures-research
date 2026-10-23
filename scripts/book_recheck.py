"""Re-check of the funded book decisions under the corrected model (night shift
2026-10-23/24, fixed before results): all RTH days in the calendar and the
LucidFlex payout rule (+$4,000 AND five days >= $150 per cycle). The five-day
rule favours legs that win often in small amounts, so earlier decisions made on
the old model are re-tested:
  base       no ORB: VG + Z + RS, flat 3 (recommendation)
  flat 2 / flat 4
  no RS      VG + Z
  Z no gate  noise without the 20d-vol gate
  + ORB      today's book
Paired block bootstrap, 24 months, 2018-21 / 2022-25.
Usage: book_recheck.py DATA_DIR
"""
from __future__ import annotations

import random
import statistics as st
import sys

sys.path.insert(0, "scripts")
import gate_check as G  # noqa: E402
import funded_sprint as F  # noqa: E402
from mc_runs import sized  # noqa: E402
from mc_book import HORIZON, BLOCK  # noqa: E402
from score_cond_bracket import parse  # noqa: E402

BOOK = {"f1": "book", "rp": "book"}


def main():
    data = sys.argv[1]
    g, zf = G.build(data, set()), G.build(data, {"Z"})
    V = {"base": sized(g, {"VG": 3, "Z": 3, "RS": 3}), "flat 2": sized(g, {"VG": 2, "Z": 2, "RS": 2}),
         "flat 4": sized(g, {"VG": 4, "Z": 4, "RS": 4}), "no RS": sized(g, {"VG": 3, "Z": 3}),
         "Z no gate": sized(zf, {"VG": 3, "Z": 3, "RS": 3}), "+ ORB": sized(g, {"ORB": 3, "VG": 3, "Z": 3, "RS": 3})}
    full = sorted({r["date"] for r in parse([f"{data}/CBA_tags.txt"])})
    for lo, hi, lab in (("2018", "2022", "2018-21"), ("2022", "2026", "2022-25")):
        cal = [d for d in full if lo <= d < hi]
        rnd = random.Random(4242)
        paths = []
        for _ in range(4000):
            idx = []
            while len(idx) < HORIZON:
                s = rnd.randrange(0, len(cal) - BLOCK)
                idx.extend(range(s, s + BLOCK))
            paths.append(idx[:HORIZON])
        print(f"--- {lab}")
        base = None
        for name, tr in V.items():
            by = {}
            for t in tr:
                by.setdefault(t[0], []).append(t)
            days = [([t[3] for t in sorted(by.get(d, []), key=lambda t: t[2])], None, None) for d in cal]
            fp = [x for x in (F.run_path(days[s:], BOOK, True) for s in range(len(days) - 250)) if x]
            cash = [F.run_path([days[i] for i in p], BOOK) for p in paths]
            base = base or cash
            d = [x - y for x, y in zip(cash, base)]
            print(f"   {name:<10} mean ${st.mean(cash):7,.0f} vs base {st.mean(d):+6,.0f} (+/- {1.96 * st.pstdev(d) / len(d) ** 0.5:,.0f}) "
                  f"better/worse {sum(x > 0 for x in d) / len(d) * 100:3.0f}/{sum(x < 0 for x in d) / len(d) * 100:3.0f}% | "
                  f"first payout {sum(r for r, _ in fp) / len(fp) * 100:4.1f}%")


if __name__ == "__main__":
    main()
