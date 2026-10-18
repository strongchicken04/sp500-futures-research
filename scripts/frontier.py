"""Size versus breadth: is it better to add contracts or add strategies?

At 3 MNQ the book already busts about a quarter of evaluations, so a signal
with positive, stable expectancy can still lower pass rate when added -- it
adds variance on top of a position that is already near its limit. The
alternative is to carry more uncorrelated signals at a smaller size. This
compares the two on the measures that matter with no deadline: pass rate,
bust rate and how long a pass takes.
"""
from __future__ import annotations

import csv
import sys

sys.path.insert(0, "scripts")
from prop_sim import Trade, simulate, merge, TIERS  # noqa: E402
from score_multi import parse_ms, to_tr, load_book, STOP_PCT, TGT_PCT  # noqa: E402

SPLIT = "2022-01-01"


def main() -> None:
    sp = sys.argv[1]
    reg = {}
    with open("results/nq_panel_real.csv") as fh:
        for r in csv.DictReader(fh):
            try:
                reg[r["date"]] = float(r["rvol20"])
            except (ValueError, KeyError):
                continue

    def gate(ts):
        return [t for t in ts if reg.get(t.date, 9.0) < 0.30]

    book = load_book(sp, gate)
    ms = parse_ms(f"{sp}/MSX1_tags.txt")
    onlr = gate(to_tr(ms["ONLR"], STOP_PCT.index(0.0012), None, "ONLR"))
    pm13 = gate(to_tr(ms["PM13"], STOP_PCT.index(0.0012), None, "PM13"))

    ports = {
        "book": book,
        "book+PM13": merge(book, pm13),
        "book+ONLR": merge(book, onlr),
        "book+PM13+ONLR": merge(book, pm13, onlr),
    }
    sizes = [("1.5 MNQ", 3.0, 200.0), ("2 MNQ", 4.0, 240.0),
             ("2.5 MNQ", 5.0, 270.0), ("3 MNQ", 6.0, 300.0)]
    orig = list(TIERS)
    print(f"{'portfolio':<16} {'size':<8} | {'full pass/bust/med':>20} | "
          f"{'OOS pass/bust/med':>20}")
    for pn, ts in ports.items():
        for sn, dpp, ds in sizes:
            TIERS.clear()
            TIERS.append((0.0, dpp, ds))
            f = simulate(ts, window=250, day_stop_profit=1450.0)
            o = simulate([t for t in ts if t.date >= SPLIT], window=250,
                         day_stop_profit=1450.0)
            print(f"{pn:<16} {sn:<8} | {f.pass_rate:6.1f}/{f.bust_rate:5.1f}/"
                  f"{f.median_days:4.0f} | {o.pass_rate:6.1f}/{o.bust_rate:5.1f}/"
                  f"{o.median_days:4.0f}")
        print()
    TIERS.clear()
    TIERS.extend(orig)


if __name__ == "__main__":
    main()
