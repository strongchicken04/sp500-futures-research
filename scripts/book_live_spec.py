"""The book measured on the rules actually traded (live-spec exports).

  research   ORB (fill-fixed) + VWAP band research export (up to 2 trades a
             day) + noise momentum research export   (book_after_fix 'fixed, no Dow')
  live now   ORB + Lucid 2 as written (plain VWAP cross, 5-min chart) + Lucid 6
  live fixed ORB + Lucid 2 changed to the 0.20% band break (first trade only)
             + Lucid 6 with the 0.50% hard stop
Vol gate (prior-day 20d realised vol < 0.30) on the VWAP and noise legs as in
the indicators; ORB as in book_after_fix. Costs as in score_live_spec.

Usage: book_live_spec.py FIXED_DIR SCRATCH_DIR
"""
from __future__ import annotations

import datetime as dt
import sys

sys.path.insert(0, "scripts")
from prop_sim import Trade, merge  # noqa: E402
from rescore_all import rvol  # noqa: E402
from mixed_accounts import calendar_days, sim_groups  # noqa: E402
from final_lifecycle import staged, lad, stage_line  # noqa: E402
from book_after_fix import parts, to_usd  # noqa: E402
from score_live_spec import parse  # noqa: E402


def leg(T, k, tag):
    return [Trade(t["date"], t["pts"], tag) for t in T[k] if 0 < t["rv"] < 0.30]


def main():
    fixed, sp = sys.argv[1], sys.argv[2]
    reg = rvol()
    orb, vg, ym, nz = parts(fixed, reg)
    T = parse([f"{sp}/LSVWAP_tags.txt", f"{sp}/LSNOISE_tags.txt"])
    books = {
        "research": merge(merge(to_usd(orb), to_usd(vg)), to_usd(nz)),
        "live now": merge(merge(to_usd(orb), to_usd(leg(T, "P5", "VG"))), to_usd(leg(T, "N0", "Z"))),
        "live fixed": merge(merge(to_usd(orb), to_usd(leg(T, "B5", "VG"))), to_usd(leg(T, "NS", "Z"))),
        "fixed, no ORB": merge(to_usd(leg(T, "B5", "VG")), to_usd(leg(T, "NS", "Z"))),
    }
    for lab, ts in books.items():
        ts = [t for t in ts if dt.date.fromisoformat(t.date).weekday() != 2 or t.strat == "Z"]
        cal = sorted(set(t.date for t in ts))
        d = calendar_days(ts, cal)
        T3 = staged(d, lad(400, 4, 75), lad(500, 4, 75), lad(400, 4, 75))
        stage_line(f"{lab:<14} ladder K400/500/400", T3)
        r = sim_groups([(5, T3)])
        print(f"      5 accounts 24m: p10 {r['p10']:,.0f}  median {r['p50']:,.0f}  p90 {r['p90']:,.0f}\n")


if __name__ == "__main__":
    main()
