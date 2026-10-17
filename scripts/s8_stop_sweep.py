"""Price every candidate stop definition for the gap reversal from one backtest.

The 15-point stop was fitted where NQ traded near 5,000, which made it 0.30%
of price; at 22,000 the same number is 0.07%. A stop that is not expressed
relative to price or volatility silently tightens as the index rises, so the
question is not only how wide the stop should be but what it should be a
fraction of. The exporter records the first bar each candidate level was
breached, which is enough to reconstruct the realised P&L of any of them
offline.
"""
from __future__ import annotations

import csv
import statistics as st
import sys

sys.path.insert(0, "scripts")
from prop_sim import Trade, simulate, merge, load_tags, TIERS  # noqa: E402
from vwap_grid_barrier import parse_grid, to_trades, SL_LVLS, TP_LVLS  # noqa: E402

STOP_PTS = [10.0, 15.0, 25.0, 40.0, 60.0, 90.0]
STOP_PCT = [0.0005, 0.0010, 0.0020, 0.0035, 0.0050]
STOP_ATR = [0.25, 0.50, 0.75, 1.00, 1.50]


def parse(path: str) -> list[dict]:
    out = []
    with open(path) as fh:
        for line in fh:
            p = line.strip().split(",")
            if len(p) < 23 or p[0] != "S8M":
                continue
            try:
                out.append({
                    "date": p[1].split(" ")[0],
                    "gap": float(p[2]), "entry": float(p[3]),
                    "atr": float(p[4]),
                    "pt": [int(x) for x in p[5:11]],
                    "pct": [int(x) for x in p[11:16]],
                    "atrb": [int(x) for x in p[16:21]],
                    "mae": float(p[21]), "eod": float(p[22]),
                })
            except (ValueError, IndexError):
                continue
    return out


def trades_for(rows: list[dict], kind: str, i: int) -> list[Trade]:
    out = []
    for r in rows:
        if kind == "pt":
            hit, size = r["pt"][i], STOP_PTS[i]
        elif kind == "pct":
            hit, size = r["pct"][i], r["entry"] * STOP_PCT[i]
        else:
            hit, size = r["atrb"][i], r["atr"] * STOP_ATR[i]
        out.append(Trade(r["date"], -size if hit >= 0 else r["eod"], "S8"))
    return out


def label(kind: str, i: int) -> str:
    if kind == "pt":
        return f"{STOP_PTS[i]:.0f} pt"
    if kind == "pct":
        return f"{STOP_PCT[i]*100:.2f}% of price"
    return f"{STOP_ATR[i]:.2f} x ATR"


def main() -> None:
    sp = sys.argv[1]
    rows = parse(f"{sp}/s8mae_tags.txt")
    print(f"{len(rows)} gap-reversal trades with excursion data")
    print(f"entry price range {min(r['entry'] for r in rows):.0f} - "
          f"{max(r['entry'] for r in rows):.0f}\n")

    reg = {}
    with open("results/nq_panel_real.csv") as fh:
        for r in csv.DictReader(fh):
            try:
                reg[r["date"]] = float(r["rvol20"])
            except (ValueError, KeyError):
                continue

    s1 = load_tags(f"{sp}/s1_tags.txt", fmt="s1")
    grid = parse_grid(f"{sp}/vg_tags.txt")
    vwap = to_trades(grid, SL_LVLS.index(25.0), TP_LVLS.index(100.0))
    monfri = [t for t in load_tags(f"{sp}/combo_tags.txt", fmt="combo")
              if t.strat == "MONFRI"]

    def gate(ts):
        return [t for t in ts if reg.get(t.date, 9.0) < 0.30]

    base = merge(gate(s1), gate(vwap), gate(monfri))
    orig = list(TIERS)
    TIERS.clear()
    TIERS.extend([(0.0, 4.0, 240.0)])

    b80 = simulate(base, window=80, day_stop_profit=1450.0)
    b120 = simulate(base, window=120, day_stop_profit=1450.0)
    print(f"portfolio without the gap reversal: "
          f"80d {b80.pass_rate:.1f}%/{b80.bust_rate:.1f}%   "
          f"120d {b120.pass_rate:.1f}%/{b120.bust_rate:.1f}%\n")

    print(f"{'stop definition':<20} {'WR':>6} {'avg':>7} {'avgL':>7} "
          f"{'24-25':>7} | {'80d':>13} {'120d':>13}")
    results = []
    for kind, levels in (("pt", STOP_PTS), ("pct", STOP_PCT), ("atr", STOP_ATR)):
        for i in range(len(levels)):
            ts = trades_for(rows, kind, i)
            v = [t.points for t in ts]
            w = [x for x in v if x > 0]
            l = [x for x in v if x <= 0]
            rec = [t.points for t in ts if t.date >= "2024-01-01"]
            port = merge(base, gate(ts))
            r80 = simulate(port, window=80, day_stop_profit=1450.0)
            r120 = simulate(port, window=120, day_stop_profit=1450.0)
            results.append((label(kind, i), r80.pass_rate, r120.pass_rate))
            print(f"{label(kind, i):<20} {len(w)/len(v)*100:5.1f}% "
                  f"{st.mean(v):+7.2f} {st.mean(l) if l else 0:+7.1f} "
                  f"{st.mean(rec) if rec else 0:+7.2f} | "
                  f"{r80.pass_rate:6.1f}/{r80.bust_rate:4.1f} "
                  f"{r120.pass_rate:6.1f}/{r120.bust_rate:4.1f}")

    best = max(results, key=lambda x: x[1])
    print(f"\nbest at 80 days: {best[0]} ({best[1]:.1f}%, "
          f"{best[1] - b80.pass_rate:+.1f}pp over no gap reversal)")

    TIERS.clear()
    TIERS.extend(orig)


if __name__ == "__main__":
    main()
