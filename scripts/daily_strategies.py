"""Backtest the daily-resolution candidates from the literature review.

Three of the researched strategies need only daily OHLC, so they can be
tested here against the local panel instead of waiting on a cloud backtest:

  TOM   turn-of-the-month long (Carcano & Tornero, via Quantpedia)
  REV   long after an outsized down session (Dunis, Laws & Rudy 2011, JAM 12(3))
  CO_OC overnight-to-intraday reversal (Della Corte & Kosowski)

Every one is scored on the barrier metric, not on total points, because a
strategy that earns more but loses in clusters is worth less here.
"""
from __future__ import annotations

import csv
import statistics as st
import sys

sys.path.insert(0, "scripts")
from prop_sim import Trade, simulate, merge, report, TIERS  # noqa: E402


def load_panel(path: str) -> list[dict]:
    out = []
    with open(path) as fh:
        for r in csv.DictReader(fh):
            try:
                out.append({
                    "date": r["date"],
                    "o": float(r["open"]), "h": float(r["high"]),
                    "l": float(r["low"]), "c": float(r["close"]),
                    "atr": float(r["atr14"]) if r.get("atr14") else None,
                    "dow": int(float(r["dow"])) if r.get("dow") else None,
                })
            except (ValueError, KeyError):
                continue
    return out


def turn_of_month(bars: list[dict], stop_pct: float = 0.005) -> list[Trade]:
    """Long the cash open, flat at the close, on the last session of the
    month and the first three of the next."""
    out = []
    for i, b in enumerate(bars):
        mm = b["date"][5:7]
        is_last = i + 1 < len(bars) and bars[i + 1]["date"][5:7] != mm
        day_of_month_idx = None
        if i > 0 and bars[i - 1]["date"][5:7] != mm:
            day_of_month_idx = 0
        elif i > 1 and bars[i - 2]["date"][5:7] != mm:
            day_of_month_idx = 1
        elif i > 2 and bars[i - 3]["date"][5:7] != mm:
            day_of_month_idx = 2
        if not (is_last or day_of_month_idx is not None):
            continue
        stop = b["o"] * (1 - stop_pct)
        pts = (stop - b["o"]) if b["l"] <= stop else (b["c"] - b["o"])
        out.append(Trade(b["date"], pts, "TOM"))
    return out


def reversal_after_drop(bars: list[dict], z: float = 1.5,
                        stop_pct: float = 0.009) -> list[Trade]:
    """Buy the close after a session whose return is more than z stdevs below
    zero, exit at the next open. Fires on exactly the days the momentum book
    is bleeding, which is the point of carrying it."""
    out = []
    rets = []
    for i in range(1, len(bars) - 1):
        prev, cur, nxt = bars[i - 1], bars[i], bars[i + 1]
        rets.append((cur["c"] - prev["c"]) / prev["c"])
        if len(rets) < 21:
            continue
        sd = st.pstdev(rets[-20:])
        day_ret = (cur["c"] - cur["o"]) / cur["o"]
        if sd <= 0 or day_ret >= -z * sd:
            continue
        entry = cur["c"]
        stop = entry * (1 - stop_pct)
        pts = (stop - entry) if nxt["l"] <= stop else (nxt["o"] - entry)
        out.append(Trade(nxt["date"], pts, "REV"))
    return out


def overnight_reversal(bars: list[dict], lo: float = -0.0025,
                       hi: float = 0.0040) -> list[Trade]:
    """Fade the overnight gap: long after a weak one, short after a strong
    one, flat at the close. Stop is one gap-width beyond entry, so the loss
    is known at the moment of entry."""
    out = []
    for i in range(1, len(bars)):
        prev, cur = bars[i - 1], bars[i]
        gap = (cur["o"] - prev["c"]) / prev["c"]
        if lo < gap < hi:
            continue
        size = abs(cur["o"] - prev["c"])
        if gap <= lo:
            stop = cur["o"] - size
            pts = (stop - cur["o"]) if cur["l"] <= stop else (cur["c"] - cur["o"])
        else:
            stop = cur["o"] + size
            pts = -(stop - cur["o"]) if cur["h"] >= stop else -(cur["c"] - cur["o"])
        out.append(Trade(cur["date"], pts, "CO_OC"))
    return out


def stats(name: str, ts: list[Trade]) -> None:
    if not ts:
        print(f"{name:<12} no trades")
        return
    p = [t.points for t in ts]
    w = [x for x in p if x > 0]
    l = [x for x in p if x <= 0]
    print(f"{name:<12} n={len(p):5d} WR={len(w)/len(p)*100:4.1f}% "
          f"avg={st.mean(p):+6.2f} avgW={st.mean(w) if w else 0:+6.1f} "
          f"avgL={st.mean(l) if l else 0:+6.1f} worst={min(p):+7.1f} "
          f"sum={sum(p):+8.0f}")


def main() -> None:
    bars = load_panel(sys.argv[1])
    print(f"{len(bars)} daily bars  {bars[0]['date']} -> {bars[-1]['date']}\n")

    tom = turn_of_month(bars)
    rev = reversal_after_drop(bars)
    coc = overnight_reversal(bars)

    print("--- trade statistics ---")
    for n, t in [("TOM", tom), ("REV", rev), ("CO_OC", coc)]:
        stats(n, t)

    orig = list(TIERS)
    TIERS.clear()
    TIERS.extend([(0.0, 4.0, 240.0)])  # flat 2 MNQ, the policy that wins

    print("\n--- barrier metric, 2 MNQ flat, 80-day window ---")
    for n, t in [("TOM alone", tom), ("REV alone", rev), ("CO_OC alone", coc),
                 ("TOM+REV", merge(tom, rev)),
                 ("TOM+REV+CO_OC", merge(tom, rev, coc))]:
        print("  " + report(n, simulate(t, window=80, day_stop_profit=1450.0)))

    TIERS.clear()
    TIERS.extend(orig)


if __name__ == "__main__":
    main()
