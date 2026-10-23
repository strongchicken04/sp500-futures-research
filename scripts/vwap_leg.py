"""VWAP-side leg for the funded book (2026-10-23, fixed before results): every
day at 11:00 (and variant 10:00), long above the session VWAP / short below,
bracket +0.30% / -0.50% else flat 15:55, 3 MNQ, costs 0.75 pt (+0.25 on stops),
vol gate as the other legs. Book without ORB (VG + Z + RS) + this leg, paired
bootstrap, 2018-21 / 2022-25, and 2010-13 / 2014-17 with the old exports.
Usage: vwap_leg.py DATA_DIR
"""
from __future__ import annotations

import sys

sys.path.insert(0, "scripts")
import gate_check as G  # noqa: E402
import old_check as O  # noqa: E402
from score_cond_bracket import parse, LEVELS  # noqa: E402
from b_sprint_lab import sgn  # noqa: E402
from mc_book import compare, summary  # noqa: E402
from mc_runs import sized  # noqa: E402
from rescore_all import rvol  # noqa: E402

EOD = 955


def leg(rows, typ, e_min, name, tp=30, sp=50):
    ti, si = LEVELS.index(tp), LEVELS.index(sp)
    out = []
    for r in rows:
        if r["type"] != typ:
            continue
        s = sgn(r["e"] - r["vwap"])
        if not s:
            continue
        fav, adv = (r["up"], r["dn"]) if s == 1 else (r["dn"], r["up"])
        t, sl = fav[ti], adv[si]
        T, S = r["e"] * tp / 1e4, r["e"] * sp / 1e4
        if sl >= 0 and (t < 0 or sl <= t):
            pts, x = -S - 1.0, e_min + sl
        elif t >= 0:
            pts, x = T - 0.75, e_min + t
        else:
            pts, x = s * r["eod"] - 0.75, EOD
        out.append((r["date"], e_min, min(EOD, x), pts * 2.0, name))
    return out


def main():
    data = sys.argv[1]
    reg = rvol()
    new = [t for t in leg(parse([f"{data}/CBA_tags.txt"]), "T1100", 660, "V11") + leg(parse([f"{data}/CBA_tags.txt"]), "T1000", 600, "V10")
           if reg.get(t[0], 9.0) < 0.30]
    base = [t for t in G.build(data, set()) if t[4] in ("VG", "Z", "RS")]
    tr = base + new
    cal_all = sorted({t[0] for t in tr})
    core = {"VG": 3, "Z": 3, "RS": 3}
    for lo, hi, lab in (("0", "2022", "2018-21"), ("2022", "9", "2022-25")):
        cal = [d for d in cal_all if lo <= d < hi]
        v = [t[3] for t in new if t[4] == "V11" and lo <= t[0] < hi]
        print(f"--- {lab}: V11 ${sum(v) / len(v):+.2f} per MNQ per trade (n {len(v)})")
        for line in summary(compare({"no ORB (VG+Z+RS)": sized(tr, core), "+ V11 3": sized(tr, dict(core, V11=3)),
                                     "+ V10 3": sized(tr, dict(core, V10=3))}, cal, trials=2500, seed=97), "no ORB (VG+Z+RS)"):
            print("   " + line)
    allt = O.legs(data)
    gated = {t[0] for t in allt if t[5]}
    oldrows = parse([f"{data}/CBA_OLD_tags.txt"])
    old_new = [t for t in leg(oldrows, "T1100", 660, "V11") if t[0] in gated]
    obase = [t[:5] for t in allt if t[5] and t[4] in ("VG", "Z", "RS")]
    otr = obase + old_new
    ocal = sorted({t[0] for t in otr})
    for lab, lo, hi in O.HALVES:
        cal = [d for d in ocal if lo <= d < hi]
        v = [t[3] for t in old_new if lo <= t[0] < hi]
        print(f"--- {lab}: V11 ${sum(v) / len(v):+.2f} per MNQ per trade (n {len(v)})")
        for line in summary(compare({"no ORB (VG+Z+RS)": sized(otr, core), "+ V11 3": sized(otr, dict(core, V11=3))}, cal, trials=2500, seed=97), "no ORB (VG+Z+RS)"):
            print("   " + line)


if __name__ == "__main__":
    main()
