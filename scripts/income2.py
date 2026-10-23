"""Income per funded seat, corrected model (night shift 2026-10-23).

Two corrections to income.py / mc_book (fixed before results):
  1. Calendar: mc_book draws its 20-day blocks from days WITH book trades only;
     ~21% of trading days have none (vol gate, no signal), so a 504-"day" path
     was ~2.4 calendar years. Here the calendar is every RTH day of the
     cond-bracket export (empty days included).
  2. Payout rule (LucidFlex 50K): +$4,000 AND five profitable days (>= $150)
     in the cycle (funded_sprint.run_path).
Reported for the no-ORB book and the book with ORB (flat 3), 2018-21 / 2022-25:
mean / p10 / p90 cash per seat in 24 months, first-payout rate and mean days
to it from every start day, payouts per seat.
Usage: income2.py DATA_DIR
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
    raw = G.build(data, set())
    full = sorted({r["date"] for r in parse([f"{data}/CBA_tags.txt"])})
    books = {"no ORB": sized(raw, {"VG": 3, "Z": 3, "RS": 3}), "with ORB": sized(raw, {"ORB": 3, "VG": 3, "Z": 3, "RS": 3})}
    for lo, hi, lab in (("2018", "2022", "2018-21"), ("2022", "2026", "2022-25")):
        for bname, tr in books.items():
            by = {}
            for t in tr:
                by.setdefault(t[0], []).append(t)
            for cname, cal in (("trade days", sorted(d for d in by if lo <= d < hi)), ("all days", [d for d in full if lo <= d < hi])):
                days = [([t[3] for t in sorted(by.get(d, []), key=lambda t: t[2])], None, None) for d in cal]
                for rule in (False, True):
                    F.PD_RULE = rule
                    fp = [x for x in (F.run_path(days[s:], BOOK, True) for s in range(len(days) - 250)) if x]
                    ok = [d for r, d in fp if r]
                    rnd = random.Random(137)
                    cash = []
                    for _ in range(3000):
                        idx = []
                        while len(idx) < HORIZON:
                            s = rnd.randrange(0, len(days) - BLOCK)
                            idx.extend(range(s, s + BLOCK))
                        cash.append(F.run_path([days[i] for i in idx[:HORIZON]], BOOK))
                    sv = sorted(cash)
                    m = st.mean(cash)
                    print(f"{lab} {bname:<8} {cname:<10} 5-day rule {'on ' if rule else 'off'}: mean ${m:7,.0f} (${m / 24:5,.0f}/month) "
                          f"p10 ${sv[len(sv) // 10]:7,.0f} p90 ${sv[9 * len(sv) // 10]:7,.0f} | first payout {len(ok) / len(fp) * 100:4.1f}% "
                          f"in {st.mean(ok):4.1f} d")


if __name__ == "__main__":
    main()
