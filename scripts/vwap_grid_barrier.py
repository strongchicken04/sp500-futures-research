"""Re-score the VWAP SL/TP grid on the barrier metric instead of total P&L.

The grid dump records, per trade, the first bar at which each SL and each TP
threshold was breached. That is enough to reconstruct the realised P&L of any
(SL, TP) pair offline, so all 49 cells can be swept without re-running a
backtest. The previous pass picked a cell by total points; a challenge account
cares about first-passage probability, which can rank cells very differently.
"""
from __future__ import annotations

import sys

sys.path.insert(0, "scripts")
from prop_sim import Trade, simulate, merge, report, load_tags  # noqa: E402

SL_LVLS = [15.0, 25.0, 40.0, 60.0, 75.0, 100.0, 150.0]
TP_LVLS = [15.0, 25.0, 40.0, 60.0, 100.0, 150.0, 200.0]


def parse_grid(path: str) -> list[dict]:
    rows = []
    with open(path) as fh:
        for line in fh:
            p = line.strip().split(",")
            if len(p) < 20 or p[0] != "VG":
                continue
            try:
                rows.append({
                    "date": p[1].split(" ")[0],
                    "dir": int(p[2]),
                    "entry": float(p[3]),
                    "sl": [int(x) for x in p[4:11]],
                    "tp": [int(x) for x in p[11:18]],
                    "eod": float(p[18]),
                })
            except (ValueError, IndexError):
                continue
    return rows


def pnl_for(row: dict, sl_i: int, tp_i: int) -> float:
    """Realised points for one trade under a given (SL, TP) pair."""
    sl_bar = row["sl"][sl_i]
    tp_bar = row["tp"][tp_i]
    sl_hit = sl_bar >= 0
    tp_hit = tp_bar >= 0

    if sl_hit and tp_hit:
        # Whichever came first wins. Ties resolve against us (conservative).
        return -SL_LVLS[sl_i] if sl_bar <= tp_bar else TP_LVLS[tp_i]
    if sl_hit:
        return -SL_LVLS[sl_i]
    if tp_hit:
        return TP_LVLS[tp_i]
    return row["eod"]


def to_trades(rows: list[dict], sl_i: int, tp_i: int) -> list[Trade]:
    return [Trade(r["date"], pnl_for(r, sl_i, tp_i), "VWAP") for r in rows]


def main() -> None:
    grid_path, s1_path = sys.argv[1], sys.argv[2]
    rows = parse_grid(grid_path)
    print(f"parsed {len(rows)} VWAP grid trades\n")

    s1 = load_tags(s1_path, fmt="s1")

    results = []
    for si, sl in enumerate(SL_LVLS):
        for ti, tp in enumerate(TP_LVLS):
            tr = to_trades(rows, si, ti)
            solo = simulate(tr)
            with_s1 = simulate(merge(s1, tr))
            tot = sum(t.points for t in tr)
            results.append({
                "sl": sl, "tp": tp,
                "solo_pass": solo.pass_rate, "solo_bust": solo.bust_rate,
                "combo_pass": with_s1.pass_rate, "combo_bust": with_s1.bust_rate,
                "total_pts": tot,
            })

    base = simulate(s1)
    print(f"BASELINE  S1 alone: pass {base.pass_rate:.1f}%  bust {base.bust_rate:.1f}%\n")

    print("=== ranked by COMBO pass rate (S1 + VWAP cell) ===")
    print(f"{'SL':>5} {'TP':>5} | {'solo pass':>9} {'solo bust':>9} | "
          f"{'combo pass':>10} {'combo bust':>10} | {'tot pts':>9}")
    for r in sorted(results, key=lambda x: -x["combo_pass"])[:15]:
        flag = "  <-- beats S1 alone" if r["combo_pass"] > base.pass_rate else ""
        print(f"{r['sl']:5.0f} {r['tp']:5.0f} | {r['solo_pass']:8.1f}% {r['solo_bust']:8.1f}% | "
              f"{r['combo_pass']:9.1f}% {r['combo_bust']:9.1f}% | {r['total_pts']:9.0f}{flag}")

    print("\n=== ranked by TOTAL POINTS (what the old pass optimised) ===")
    for r in sorted(results, key=lambda x: -x["total_pts"])[:8]:
        print(f"{r['sl']:5.0f} {r['tp']:5.0f} | {r['solo_pass']:8.1f}% {r['solo_bust']:8.1f}% | "
              f"{r['combo_pass']:9.1f}% {r['combo_bust']:9.1f}% | {r['total_pts']:9.0f}")

    print("\n=== best VWAP cell standalone ===")
    for r in sorted(results, key=lambda x: -x["solo_pass"])[:8]:
        print(f"{r['sl']:5.0f} {r['tp']:5.0f} | {r['solo_pass']:8.1f}% {r['solo_bust']:8.1f}% | "
              f"{r['combo_pass']:9.1f}% {r['combo_bust']:9.1f}% | {r['total_pts']:9.0f}")


if __name__ == "__main__":
    main()
