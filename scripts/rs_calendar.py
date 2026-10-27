"""RS leg x calendar (night 2026-10-27/28, E10 leftovers, fixed before
results): first RS signal of the day (live rule), funded leg +/-1.25% gross
bp and sprint 0.20/0.30 resolved win rate, split by
  weekday Mon..Fri, and month position: first 3 trading days of the month
  (month-start flows) vs the rest.
Four eras + 2026. A calendar rule is adopted only if the pattern holds in all
four eras (it is a 5-way split - expect noise).
Usage: rs_calendar.py DATA_DIR
"""
from __future__ import annotations

import datetime as dt
import sys

sys.path.insert(0, "scripts")
from rs_buckets import ERAS, cell  # noqa: E402
from score_multi_feature import parse as parse_mf, first_signals  # noqa: E402


def main():
    data = sys.argv[1]
    for lab, lo, hi, suf in ERAS:
        allsig = first_signals(parse_mf(f"{data}/MFEAT{suf}_tags.txt"), lambda r: 1 if (r["rs"] > 0.0015 and r["vwapd"] > 0) else
                               (-1 if (r["rs"] < -0.0015 and r["vwapd"] < 0) else 0))
        alld = sorted({r["date"] for r in parse_mf(f"{data}/MFEAT{suf}_tags.txt")})
        rank, prev = {}, None
        for d in alld:
            k = 0 if prev is None or d[:7] != prev[:7] else rank[prev] + 1
            rank[d], prev = k, d
        sig = {d: v for d, v in allsig.items() if lo <= d < hi}
        print(f"--- {lab}")
        for wd, nm in enumerate(("Mon", "Tue", "Wed", "Thu", "Fri")):
            print(f"   {nm}           " + cell([v for d, v in sig.items() if dt.date.fromisoformat(d).weekday() == wd]))
        print("   month day 1-3 " + cell([v for d, v in sig.items() if rank.get(d, 9) < 3]))
        print("   rest          " + cell([v for d, v in sig.items() if rank.get(d, 9) >= 3]))


if __name__ == "__main__":
    main()
