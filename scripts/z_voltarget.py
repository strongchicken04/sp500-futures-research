"""Vol-targeted size for the noise leg (fixed 2026-10-23): MNQ = round(3 x
0.20 / rv20) clipped to 1..5 (rv20 = prior-day 20d realised vol), vs flat 3;
book without ORB (VG 3 + Z + RS 3); paired bootstrap, 2018-21 / 2022-25 and
2010-13 / 2014-17.
Usage: z_voltarget.py DATA_DIR
"""
from __future__ import annotations

import sys

sys.path.insert(0, "scripts")
import gate_check as G  # noqa: E402
import old_check as O  # noqa: E402
from score_live_spec import parse as parse_ls  # noqa: E402
from mc_book import compare, summary  # noqa: E402


def zsize(rv):
    return max(1, min(5, round(3 * 0.20 / rv))) if rv > 0 else 3


def books(base, rvmap):
    flat = [(d, e, x, u * 3, leg) for d, e, x, u, leg in base]
    vt = [(d, e, x, u * (zsize(rvmap.get(d, 0.2)) if leg == "Z" else 3), leg) for d, e, x, u, leg in base]
    return {"flat 3": flat, "Z vol-targeted": vt}


def main():
    data = sys.argv[1]
    T = parse_ls([f"{data}/LSNOISE_tags.txt", f"{data}/LSNOISE_OLD_tags.txt"])
    rvmap = {t["date"]: t["rv"] for t in T["NS"] if t["rv"] > 0}
    new = [t for t in G.build(data, set()) if t[4] in ("VG", "Z", "RS")]
    allt = O.legs(data)
    old = [t[:5] for t in allt if t[5] and t[4] in ("VG", "Z", "RS")]
    for tr, halves in ((new, (("2018-21", "0", "2022"), ("2022-25", "2022", "9"))), (old, O.HALVES)):
        cal_all = sorted({t[0] for t in tr})
        B = books(tr, rvmap)
        for lab, lo, hi in halves:
            cal = [d for d in cal_all if lo <= d < hi]
            sizes = [zsize(rvmap.get(d, 0.2)) for d in cal]
            print(f"--- {lab}: Z size mean {sum(sizes) / len(sizes):.2f}")
            for line in summary(compare(B, cal, trials=2500, seed=139), "flat 3"):
                print("   " + line)


if __name__ == "__main__":
    main()
