"""Book add-ons (queue item 10): the overnight-low touch on gap-up days
(onl_gapup_book rule: gap >= 0.25%, buy the first RTH touch of the overnight
low, +0.25% / -0.40%, else 15:55; vol gate) added at 1 and 2 MNQ per unit to
the fixed live book (ORB + Lucid 2 band + Lucid 6 with stop). The FOMC fade
(8 trades a year) is too rare to move the book and is left out.

Usage: book_addons.py FIXED_DIR SCRATCH_DIR
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
from score_live_spec import parse as parse_ls  # noqa: E402
from score_cond_bracket import parse, add_daily  # noqa: E402
from onl_gapup_book import pts  # noqa: E402


def main():
    fixed, sp = sys.argv[1], sys.argv[2]
    reg = rvol()
    orb, _, _, _ = parts(fixed, reg)
    T = parse_ls([f"{sp}/LSVWAP_tags.txt", f"{sp}/LSNOISE_tags.txt"])
    leg = lambda k, tag: [Trade(t["date"], t["pts"], tag) for t in T[k] if 0 < t["rv"] < 0.30]
    base = merge(merge(to_usd(orb), to_usd(leg("B5", "VG"))), to_usd(leg("NS", "Z")))
    rows = parse([f"{sp}/CBC_tags.txt"])
    add_daily(rows)
    onl = [(r["date"], pts(r) - 0.75) for r in rows if r["type"] == "ONL" and r["gap"] >= 0.0025 and reg.get(r["date"], 9.0) < 0.30]
    a = [p for d, p in onl if d < "2022"]
    b = [p for d, p in onl if d >= "2022"]
    print(f"ONL gap-up: {len(onl)} trades, {sum(a) / len(a):+.2f} / {sum(b) / len(b):+.2f} pt per trade (2018-21 / 2022-25)\n")
    for n in (0, 1, 2):
        ts = merge(base, [Trade(d, p * 2.0 * n, "ONL") for d, p in onl]) if n else base
        ts = [t for t in ts if dt.date.fromisoformat(t.date).weekday() != 2 or t.strat in ("Z", "ONL")]
        cal = sorted(set(t.date for t in ts))
        T3 = staged(calendar_days(ts, cal), lad(400, 4, 75), lad(500, 4, 75), lad(400, 4, 75))
        stage_line(f"live fixed + ONL {n} MNQ/unit", T3)
        r = sim_groups([(5, T3)])
        print(f"      5 accounts 24m: p10 {r['p10']:,.0f}  median {r['p50']:,.0f}  p90 {r['p90']:,.0f}")


if __name__ == "__main__":
    main()
