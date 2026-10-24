"""Where does funded size stop paying? Integrated seat model (evaluations
simulated on the same path, two-account plan RS + 09:31), book VG + Z + RS +
V10 at 2 / 3 / 4 / 5 / 6 / 8 MNQ per leg, open-P&L check (day shift
2026-10-24). If cash kept rising to 8 the model would be rewarding variance
without limit - a warning sign about the model, not a recommendation.
Usage: seat_size.py DATA_DIR
"""
from __future__ import annotations

import sys

sys.path.insert(0, "scripts")
import integrated_seat as I  # noqa: E402

if __name__ == "__main__":
    I.PLANS = ("E1 RS + 09:31 (guard)",)
    for n in (2, 3, 4, 5, 6, 8):
        I.SIZE = n
        print(f"=== {n} MNQ per leg")
        I.main()
