"""Noise leg (Z, Lucid 6 with the 0.50% hard stop) with and without the vol gate
(prior-day 20d realised vol < 0.30) in the funded book; the original paper has
no gate. Time-aware sim at flat 3 MNQ per leg (day shift 2026-10-23).
Usage: z_gate.py DATA_DIR
"""
from __future__ import annotations

import sys

sys.path.insert(0, "scripts")
from timed_book import legs, days_for, outcomes, life  # noqa: E402
from score_live_spec import parse as parse_ls  # noqa: E402
from rescore_all import rvol  # noqa: E402


def main():
    data = sys.argv[1]
    base = legs(f"{data}/fixed", data)
    T = parse_ls([f"{data}/LSNOISE_tags.txt"])
    z_all = [(t["date"], t["ehm"], t["xhm"], t["pts"] * 2.0, "Z") for t in T["NS"]]
    reg = rvol()
    hi = sum(1 for t in z_all if not (0 < reg.get(t[0], 9.0) < 0.30))
    print(f"Z trades on gated-out days: {hi} of {len(z_all)}")
    variants = {"Z gated (now)": base, "Z without gate": [t for t in base if t[4] != "Z"] + z_all}
    for use in (("ORB", "VG", "Z", "RS"), ("ORB", "VG", "Z")):
        for name, tr in variants.items():
            cal = sorted({t[0] for t in base} | {t[0] for t in z_all})
            res, hit = [], []
            for lo, hi_ in (("0", "2022"), ("2022", "9")):
                c = [d for d in cal if lo <= d < hi_]
                dd = days_for(tr, c, 3, 10 ** 9, use)
                sz = lambda room: (3.0, 10 ** 9)
                f1 = outcomes(dd, sz, window=300, start_pnl=0.0, target=4000.0, consistency=False)
                rp = outcomes(dd, sz, window=300, start_pnl=2000.0, target=4000.0, consistency=False, locked=100.0)
                res.append(life(f1, rp))
            print(f"   {'+'.join(use):<14} {name:<16} ${res[0]:8,.0f} | ${res[1]:8,.0f}")


if __name__ == "__main__":
    main()
