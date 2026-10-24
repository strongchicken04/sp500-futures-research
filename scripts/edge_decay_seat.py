"""Edge decay in the integrated seat model (day shift 2026-10-24): the mean
edge of every funded leg AND of every evaluation sprint is cut by 0 / 50 /
100 / 150% (trade-by-trade risk unchanged). Pair plan RS + 09:31, book
VG + Z + RS + V10 at 4 MNQ, open-P&L check. Shows how much of the simulated
income comes from the prop-firm structure (cheap resets, $2,000 payouts at
+$4,000) rather than from the strategies.
Usage: edge_decay_seat.py DATA_DIR
"""
from __future__ import annotations

import sys

sys.path.insert(0, "scripts")
import integrated_seat as I  # noqa: E402

if __name__ == "__main__":
    I.PLANS = ("E1 RS + 09:31 (guard)",)
    for cut in (0.0, 0.5, 1.0, 1.5):
        I.CUT = cut
        print(f"=== edge cut {int(cut * 100)}%")
        I.main()
