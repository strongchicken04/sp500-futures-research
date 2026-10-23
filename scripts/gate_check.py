"""Vol gate (prior-day 20d realised vol < 0.30) per funded leg: on vs off,
time-aware sim at flat 3 MNQ per leg, ORB+VG+Z+RS (day shift 2026-10-23).
Usage: gate_check.py DATA_DIR
"""
from __future__ import annotations

import sys

sys.path.insert(0, "scripts")
import timed_book as TB  # noqa: E402
from timed_book import days_for, outcomes, life  # noqa: E402


def build(data, ungated):
    """ORB and RS are gated through rvol(), VG and Z through the rv field of
    the live-spec tags; both switched off per leg."""
    real, real_parse = TB.rvol, TB.parse_ls
    TB.rvol = lambda: {}
    def parse_free(paths):
        T = real_parse(paths)
        for v in T.values():
            for t in v:
                t["rv"] = 0.001
        return T
    TB.parse_ls = parse_free
    try:
        free = TB.legs(f"{data}/fixed", data)
    finally:
        TB.rvol, TB.parse_ls = real, real_parse
    gated = TB.legs(f"{data}/fixed", data)
    return [t for t in gated if t[4] not in ungated] + [t for t in free if t[4] in ungated]


def main():
    data = sys.argv[1]
    use = ("ORB", "VG", "Z", "RS")
    allcal = sorted({t[0] for t in build(data, set(use))})
    for ung in ((), ("Z",), ("VG",), ("ORB",), ("RS",), ("Z", "VG"), ("Z", "VG", "ORB", "RS")):
        tr = build(data, set(ung))
        res = []
        for lo, hi in (("0", "2022"), ("2022", "9")):
            c = [d for d in allcal if lo <= d < hi]
            dd = days_for(tr, c, 3, 10 ** 9, use)
            sz = lambda room: (3.0, 10 ** 9)
            f1 = outcomes(dd, sz, window=300, start_pnl=0.0, target=4000.0, consistency=False)
            rp = outcomes(dd, sz, window=300, start_pnl=2000.0, target=4000.0, consistency=False, locked=100.0)
            res.append(life(f1, rp))
        lab = "all gated (now)" if not ung else "no gate: " + "+".join(ung)
        print(f"   {lab:<28} ${res[0]:8,.0f} | ${res[1]:8,.0f}")


if __name__ == "__main__":
    main()
