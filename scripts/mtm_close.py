"""Lenient bound of the open-P&L check (night shift 2026-10-23/24): open trades
marked at each 5-min bar CLOSE instead of the adverse extreme (mtm_check marks
all at their worst at once = strict bound). Same variants as mtm_check plus
the book with ORB at 4; four eras. Columns: closed-only check -> close-mark.
Usage: mtm_close.py DATA_DIR
"""
from __future__ import annotations

import sys

sys.path.insert(0, "scripts")
import mtm_check as C  # noqa: E402

C.MARK = "close"
C.WITH_ORB = True
C.V = dict(C.V, **{"flat 4 + ORB 4": {"VG": 4, "Z": 4, "RS": 4, "ORB": 4}})

if __name__ == "__main__":
    C.main()
