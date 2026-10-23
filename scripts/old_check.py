"""Third, untouched period 2010-2017 (day shift 2026-10-23): nothing was tuned on
it. Same rules as live / as today's candidates:
  legs  ORB (Lucid 1 live spec, O5), VG (Lucid 2 band B5), Z (Lucid 6 NS, with
        and without the vol gate), RS (MFEAT RS rule, bracket +/-1.25% else
        15:55), open drive (OD) and NR4 break from the BARS5 panel
  book  today's (ORB+VG+Z+RS, all gated) vs the proposal (VG + Z without gate
        + RS) and proposal + OD + NR4: paired bootstrap and the stage rates of
        the one-history walk, 2010-2013 and 2014-2017.
Vol gate: prior-day 20d realised vol of NQ < 0.30 (rv from the live-spec tags).

Usage: old_check.py DATA_DIR
"""
from __future__ import annotations

import datetime as dt
import math
import statistics as st
import sys
from collections import Counter

sys.path.insert(0, "scripts")
import level_lab as L  # noqa: E402
from score_live_spec import parse as parse_ls  # noqa: E402
from score_multi_feature import parse as parse_mf, first_signals, LEVELS  # noqa: E402
from rs_book import pts as rs_pts  # noqa: E402
from mc_simple import nr4  # noqa: E402
from mc_book import compare, summary  # noqa: E402
from mc_runs import sized  # noqa: E402
from timed_book import days_for, outcomes  # noqa: E402

EOD = 955
HALVES = (("2010-2013", "2010", "2014"), ("2014-2017", "2014", "2018"))


def legs(data):
    T = parse_ls([f"{data}/LSVWAP_OLD_tags.txt", f"{data}/LSNOISE_OLD_tags.txt", f"{data}/LSORB_OLD_tags.txt"])
    reg = {t["date"]: t["rv"] for k in T for t in T[k] if t["rv"] > 0}
    gated = lambda d: 0 < reg.get(d, 9.0) < 0.30
    out = []
    for k, leg in (("O5", "ORB"), ("B5", "VG"), ("NS", "Z")):
        for t in T[k]:
            out.append((t["date"], t["ehm"], t["xhm"], t["pts"] * 2.0, leg, gated(t["date"])))
    sig = first_signals(parse_mf(f"{data}/MFEAT_OLD_tags.txt"), lambda r: 1 if (r["rs"] > 0.0015 and r["vwapd"] > 0) else
                        (-1 if (r["rs"] < -0.0015 and r["vwapd"] < 0) else 0))
    ti = si = LEVELS.index(125)
    for d, (r, s) in sig.items():
        fav, adv = (r["up"], r["dn"]) if s == 1 else (r["dn"], r["up"])
        hits = [k for k in (fav[ti], adv[si]) if k >= 0]
        x = min(EOD, r["hm"] + min(hits)) if hits else EOD
        out.append((d, r["hm"], x, rs_pts(r, s, ti, si) * 2.0, "RS", gated(d)))
    L.NAMES = ("B2_0A", "B2_0B")
    days = L.load(data)
    for leg, fn in (("OD", lambda d, p: L.odrive(d, p, 0.0005, 0.0015)), ("NR", nr4(days))):
        for t in L.trades(days, fn):
            out.append((t["date"], t["ehm"], t["xhm"], t["pts"] * 2.0, leg, gated(t["date"])))
    out = [t for t in out if not (dt.date.fromisoformat(t[0]).weekday() == 2 and t[4] in ("ORB", "VG"))]
    return out


def main():
    data = sys.argv[1]
    allt = legs(data)
    print("per trade, $ per MNQ (gated unless noted):")
    for leg in ("ORB", "VG", "Z", "RS", "OD", "NR"):
        for gate in ((True, False) if leg == "Z" else (True,)):
            row = []
            for lab, lo, hi in HALVES:
                v = [t[3] for t in allt if t[4] == leg and lo <= t[0] < hi and (t[5] or not gate)]
                sd = st.pstdev(v) if len(v) > 2 else 1.0
                row.append(f"${st.mean(v):+6.2f} t{st.mean(v) / sd * math.sqrt(len(v)):+4.1f} n{len(v):>4}" if v else "n 0")
            print(f"   {leg:<4}{'' if gate else ' (no gate)':<10} {row[0]} | {row[1]}")
    g = lambda keep_free: [t[:5] for t in allt if t[5] or t[4] in keep_free]
    now = sized(g(()), {"ORB": 3, "VG": 3, "Z": 3, "RS": 3})
    prop = sized(g(("Z",)), {"VG": 3, "Z": 3, "RS": 3})
    prop2 = sized(g(("Z",)), {"VG": 3, "Z": 3, "RS": 3, "OD": 3, "NR": 3})
    cal_all = sorted({t[0] for t in allt})
    for lab, lo, hi in HALVES:
        cal = [d for d in cal_all if lo <= d < hi]
        print(f"--- {lab} ({len(cal)} days), bootstrap mean 24-month cash per account")
        for line in summary(compare({"now": now, "proposal": prop, "proposal + OD + NR4": prop2}, cal, trials=3000, seed=83), "now"):
            print("   " + line)
        for name, tr, use in (("now", now, ("ORB", "VG", "Z", "RS")), ("proposal", prop, ("VG", "Z", "RS"))):
            dd = days_for(tr, cal, 1, 10 ** 9, use)
            sz = lambda room: (1.0, 10 ** 9)
            f1 = Counter(o for o, _ in outcomes(dd, sz, window=300, start_pnl=0.0, target=4000.0, consistency=False))
            rp = Counter(o for o, _ in outcomes(dd, sz, window=300, start_pnl=2000.0, target=4000.0, consistency=False, locked=100.0))
            print(f"   {name:<10} first payout {f1['pass'] / sum(f1.values()) * 100:.0f}%, repeat payout {rp['pass'] / sum(rp.values()) * 100:.0f}%")


if __name__ == "__main__":
    main()
