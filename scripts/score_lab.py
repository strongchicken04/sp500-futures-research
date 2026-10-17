"""Re-score the lab strategy archive on the barrier metric.

Twenty strategies were backtested earlier and ranked on returns and Sharpe.
That ranking does not survive contact with a challenge account: the VWAP grid's
most profitable cell passes at 44% while a less profitable one passes at 58%,
because first-passage probability cares about the shape of the loss
distribution and total return does not. So everything in the archive gets
scored again on the metric that actually decides the outcome.

Trades are stored as fractional returns, which are converted to points against
the daily close so that a fixed contract size means the same thing throughout.
"""
from __future__ import annotations

import csv
import glob
import os
import statistics as st
import sys

sys.path.insert(0, "scripts")
from prop_sim import Trade, simulate, merge, TIERS  # noqa: E402


def load_prices(path: str) -> dict[str, float]:
    px = {}
    with open(path) as fh:
        for r in csv.DictReader(fh):
            try:
                px[r["date"]] = float(r["close"])
            except (ValueError, KeyError):
                continue
    return px


# NQ traded between 1,600 and 9,000 over the archive's 2005-2020 span but sits
# near 30,000 today, so converting a percentage return at the price of the day
# makes old trades look trivially small. Since the question is what these rules
# would be worth on the account being traded now, returns are scaled at a fixed
# present-day notional instead.
NOTIONAL = 30000.0


def load_lab(path: str, px: dict[str, float], cap: float | None) -> list[Trade]:
    name = os.path.basename(path).replace("_trades.csv", "")
    out = []
    with open(path) as fh:
        for r in csv.DictReader(fh):
            d = r["date"]
            if d not in px:
                continue
            try:
                pts = float(r["ret"]) * NOTIONAL
            except (ValueError, KeyError):
                continue
            if cap is not None:
                pts = max(pts, -cap)
            out.append(Trade(d, pts, name))
    return out


def describe(ts: list[Trade]) -> str:
    p = [t.points for t in ts]
    w = [x for x in p if x > 0]
    l = [x for x in p if x <= 0]
    return (f"n={len(p):5d} WR={len(w)/len(p)*100:4.1f}% avg={st.mean(p):+6.2f} "
            f"avgL={st.mean(l) if l else 0:+6.1f} worst={min(p):+7.0f}")


def main() -> None:
    px = load_prices("results/daily_panel.csv")
    files = sorted(glob.glob("results/lab/*_trades.csv"))
    orig = list(TIERS)
    TIERS.clear()
    TIERS.extend([(0.0, 4.0, 240.0)])  # flat 2 MNQ

    # A tighter stop is the obvious thing to try on every one of these, and it
    # cannot be tested from this archive: the files hold realised returns only.
    # Clipping a realised loss to -15 assumes the trade was exited there while
    # still keeping every winner that dipped past -15 and recovered, which
    # manufactures an edge out of nothing -- done naively it scores most of
    # these at a 100% pass rate. Re-stopping needs per-trade MAE, which is why
    # the VWAP grid dump records breach bars. These numbers are as-backtested.
    rows = []
    for f in files:
        raw = load_lab(f, px, cap=None)
        if len(raw) < 200:
            continue
        r = simulate(raw, window=80, day_stop_profit=1450.0)
        rows.append({
            "name": raw[0].strat, "desc": describe(raw),
            "pass": r.pass_rate, "bust": r.bust_rate,
            "sum": sum(t.points for t in raw),
        })

    print("=" * 100)
    print("LAB ARCHIVE RE-SCORED ON PASS RATE  (flat 2 MNQ, 80-day window, "
          "2005-2020, returns at 30k notional)")
    print("=" * 100)
    print(f"{'strategy':<26} {'stats':<52} {'pass':>7} {'bust':>6}")
    for r in sorted(rows, key=lambda x: -x["pass"]):
        print(f"{r['name']:<26} {r['desc']:<52} "
              f"{r['pass']:6.1f}% {r['bust']:5.1f}%")

    print()
    print("Ranking by total points, for contrast:")
    for r in sorted(rows, key=lambda x: -x["sum"])[:8]:
        print(f"   {r['name']:<26} {r['sum']:+9.0f} pts   "
              f"pass {r['pass']:5.1f}%  bust {r['bust']:5.1f}%")

    TIERS.clear()
    TIERS.extend(orig)


if __name__ == "__main__":
    main()
