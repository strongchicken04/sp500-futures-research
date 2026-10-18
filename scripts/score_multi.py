"""Score every signal in a multi-signal exporter dump on prop-account pass rate.

Each tag records, per firing, the first bar each %-of-price stop and target
was touched plus the 15:55 result, so every stop/target pair can be priced
offline. Two guards against fooling ourselves:

- Stop/target is chosen on 2018-2021 only and then reported on 2022-2025.
  A signal that only looks good with parameters fitted to the whole sample
  is not a signal.
- The score that matters is the change in pass rate when the signal is added
  to the existing book, not its standalone pass rate. A strategy that is good
  alone but fires on the same days the book already wins adds nothing.
"""
from __future__ import annotations

import csv
import statistics as st
import sys
from collections import defaultdict

sys.path.insert(0, "scripts")
from prop_sim import Trade, simulate, merge, load_tags, TIERS  # noqa: E402
from vwap_grid_barrier import parse_grid, to_trades, SL_LVLS, TP_LVLS  # noqa: E402
from s8_stop_sweep import parse as parse_mae, trades_for  # noqa: E402

STOP_PCT = [0.0003, 0.0005, 0.0008, 0.0012, 0.0020]
TGT_PCT = [0.0005, 0.0010, 0.0020, 0.0035, 0.0060]
SPLIT = "2022-01-01"


def parse_ms(path: str, prefix: str = "M") -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = defaultdict(list)
    with open(path) as fh:
        for line in fh:
            p = line.strip().split(",")
            if len(p) < 17 or p[0] != prefix:
                continue
            try:
                dt = p[2]
                out[p[1]].append({
                    "date": f"{dt[0:4]}-{dt[4:6]}-{dt[6:8]}",
                    "hhmm": int(dt[8:12]),
                    "dir": int(p[3]), "e": float(p[4]),
                    "sb": [int(x) for x in p[5:10]],
                    "tb": [int(x) for x in p[10:15]],
                    "xb": int(p[15]), "eod": float(p[16]),
                })
            except (ValueError, IndexError):
                continue
    return out


def pts(r: dict, si: int, ti: int | None) -> float:
    s = r["sb"][si]
    t = r["tb"][ti] if ti is not None else -1
    if s >= 0 and (t < 0 or s <= t):
        return -STOP_PCT[si] * r["e"]
    if t >= 0:
        return TGT_PCT[ti] * r["e"]
    return r["eod"]


def to_tr(rows, si, ti, name):
    return [Trade(r["date"], pts(r, si, ti), name) for r in rows]


def weekday(d: str) -> int:
    import datetime as _dt
    return _dt.date.fromisoformat(d).weekday()


def load_book(sp: str, gate):
    s1 = load_tags(f"{sp}/s1_tags.txt", fmt="s1")
    g = parse_grid(f"{sp}/vg_tags.txt")
    vwap = to_trades(g, SL_LVLS.index(25.0), TP_LVLS.index(100.0))
    monfri = [t for t in load_tags(f"{sp}/combo_tags.txt", fmt="combo")
              if t.strat == "MONFRI"]
    # Prefer the re-run that counts the entry bar: the original exporter
    # entered at the 09:30 open but only tracked from the next bar.
    import os
    fixed = f"{sp}/S8FIX_tags.txt"
    src = fixed if os.path.exists(fixed) else f"{sp}/s8mae_tags.txt"
    s8 = trades_for(parse_mae(src), "pct", 0)
    return merge(gate(s1), gate(vwap), gate(monfri), gate(s8))


def main() -> None:
    sp, tagfile = sys.argv[1], sys.argv[2]
    prefix = sys.argv[3] if len(sys.argv) > 3 else "M"
    sigs = parse_ms(tagfile, prefix)
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
    orig = list(TIERS)
    TIERS.clear()
    TIERS.extend([(0.0, 6.0, 300.0)])  # live config: 3 MNQ evaluation

    def score(ts, window):
        r = simulate(ts, window=window, day_stop_profit=1450.0)
        return r.pass_rate, r.bust_rate

    book_is = [t for t in book if t.date < SPLIT]
    book_oos = [t for t in book if t.date >= SPLIT]
    b_full = score(book, 120)
    b_is = score(book_is, 120)
    b_oos = score(book_oos, 120)
    print(f"BOOK alone (3 MNQ, 120d): full {b_full[0]:.1f}/{b_full[1]:.1f}  "
          f"IS {b_is[0]:.1f}/{b_is[1]:.1f}  OOS {b_oos[0]:.1f}/{b_oos[1]:.1f}\n")

    summary = []
    for name, rows in sorted(sigs.items()):
        rows_g = [r for r in rows if reg.get(r["date"], 9.0) < 0.30]
        is_rows = [r for r in rows_g if r["date"] < SPLIT]
        if len(rows_g) < 60:
            print(f"{name}: only {len(rows_g)} gated firings, skipped")
            continue
        # choose (stop, target) on in-sample marginal pass rate
        best = None
        for si in range(len(STOP_PCT)):
            for ti in [None] + list(range(len(TGT_PCT))):
                tr = to_tr(is_rows, si, ti, name)
                p, b = score(merge(book_is, tr), 120)
                if best is None or p > best[0]:
                    best = (p, b, si, ti)
        _, _, si, ti = best
        all_tr = to_tr(rows_g, si, ti, name)
        oos_tr = [t for t in all_tr if t.date >= SPLIT]
        v = [t.points for t in all_tr]
        w = [x for x in v if x > 0]
        losses = [x for x in v if x <= 0]
        p_oos, bu_oos = score(merge(book_oos, oos_tr), 120)
        p_full, bu_full = score(merge(book, all_tr), 120)
        alone = score(all_tr, 120)
        # weekday profile of the chosen variant
        wd = defaultdict(list)
        for t in all_tr:
            wd[weekday(t.date)].append(t.points)
        wds = " ".join(f"{'MTWRF'[k]}{st.mean(wd[k]):+.1f}" for k in range(5)
                       if wd[k])
        tstr = "EOD" if ti is None else f"{TGT_PCT[ti]*100:.2f}%"
        summary.append((p_oos - b_oos[0], name))
        print(f"{name}  n={len(v)} ({len(v)/8:.0f}/yr)  stop {STOP_PCT[si]*100:.2f}%"
              f"  target {tstr}")
        print(f"   WR {len(w)/len(v)*100:.1f}%  avg {st.mean(v):+.2f}  "
              f"avgL {st.mean(losses) if losses else 0:+.1f}  "
              f"IS avg {st.mean([t.points for t in all_tr if t.date < SPLIT]):+.2f}  "
              f"OOS avg {st.mean([t.points for t in oos_tr]) if oos_tr else 0:+.2f}")
        print(f"   alone {alone[0]:.1f}/{alone[1]:.1f}   +book full "
              f"{p_full:.1f}/{bu_full:.1f} ({p_full-b_full[0]:+.1f}pp)   "
              f"+book OOS {p_oos:.1f}/{bu_oos:.1f} ({p_oos-b_oos[0]:+.1f}pp)")
        print(f"   by weekday: {wds}\n")

    print("RANKED by out-of-sample marginal pass-rate gain:")
    for d, n in sorted(summary, reverse=True):
        print(f"   {n:<6} {d:+.1f}pp")
    TIERS.clear()
    TIERS.extend(orig)


if __name__ == "__main__":
    main()
