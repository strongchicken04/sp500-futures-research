"""Time-aware funded book simulation (queue item 12).

Every leg carries entry and exit minutes (ET):
  ORB   S1FILL tags: entry datetime + bars x 5 min        (-0.5 pt cost, vol gate)
  VG    live-spec B5 (Lucid 2 band, first trade a day)    (costs in score_live_spec)
  Z     live-spec NS (Lucid 6 with the 0.50% hard stop)
  RS    MFEAT RS rule, bracket +/-1.25%, else 15:55       (first touch minute = exit)
Within a day trades are realised in EXIT order, and a day stop only blocks
trades ENTERED after the realised day P&L reached the stop. So concurrency is
modelled honestly (unrealised P&L of open trades is ignored, as before).
Flat sizing: n MNQ per leg. Mean 24-month cash per account as in funded_sizing
(sprint evaluations: a bust costs ~$180 and ~11 days).

Usage: timed_book.py FIXED_DIR SCRATCH_DIR
"""
from __future__ import annotations

import datetime as dt
import sys
from collections import defaultdict

sys.path.insert(0, "scripts")
from prop_sim import Trade  # noqa: E402
from rescore_all import rvol  # noqa: E402
from ladder_sim import outcomes  # noqa: E402
from score_live_spec import parse as parse_ls  # noqa: E402
from score_multi_feature import parse as parse_mf, first_signals, LEVELS  # noqa: E402
from rs_book import pts as rs_pts  # noqa: E402
from funded_sizing import life  # noqa: E402

EOD = 15 * 60 + 55


def legs(fixed, sp):
    reg = rvol()
    out = []                                   # (date, entry_min, exit_min, usd per MNQ, leg)
    for raw in open(f"{fixed}/S1VW_tags.txt"):
        f = raw.strip().split(",")
        if f[0] != "S1" or len(f) < 8:
            continue
        d, hm = f[1].split(" ")
        if reg.get(d, 9.0) >= 0.30:
            continue
        e = int(hm[:2]) * 60 + int(hm[3:])
        out.append((d, e, min(EOD, e + 5 * int(f[7])), (float(f[6]) - 0.5) * 2.0, "ORB"))
    T = parse_ls([f"{sp}/LSVWAP_tags.txt", f"{sp}/LSNOISE_tags.txt"])
    for k, leg in (("B5", "VG"), ("NS", "Z")):
        for t in T[k]:
            if 0 < t["rv"] < 0.30:
                out.append((t["date"], t["ehm"], t["xhm"], t["pts"] * 2.0, leg))
    rows = parse_mf(f"{sp}/MFEAT_tags.txt")
    sig = first_signals(rows, lambda r: 1 if (r["rs"] > 0.0015 and r["vwapd"] > 0) else
                        (-1 if (r["rs"] < -0.0015 and r["vwapd"] < 0) else 0))
    ti = si = LEVELS.index(125)
    for d, (r, s) in sig.items():
        if reg.get(d, 9.0) >= 0.30:
            continue
        fav, adv = (r["up"], r["dn"]) if s == 1 else (r["dn"], r["up"])
        hits = [k for k in (fav[ti], adv[si]) if k >= 0]
        x = min(EOD, r["hm"] + min(hits)) if hits else EOD
        out.append((d, r["hm"], x, rs_pts(r, s, ti, si) * 2.0, "RS"))
    keep = []
    for t in out:
        if dt.date.fromisoformat(t[0]).weekday() == 2 and t[4] not in ("Z", "RS"):
            continue
        keep.append(t)
    return keep


def days_for(trades, cal, n, ds, use):
    by = defaultdict(list)
    for t in trades:
        if t[4] in use:
            by[t[0]].append(t)
    days = []
    for d in cal:
        v = by.get(d, [])
        taken = []
        for t in sorted(v, key=lambda t: t[1]):              # in entry order
            realised = sum(x[3] * n for x in taken if x[2] <= t[1])
            if realised <= -ds:
                continue
            taken.append(t)
        days.append((d, [Trade(d, t[3], t[4]) for t in sorted(taken, key=lambda t: t[2])]))
    return days


def main():
    fixed, sp = sys.argv[1], sys.argv[2]
    tr = legs(fixed, sp)
    cal_all = sorted({t[0] for t in tr})
    books = {"ORB+VG+Z": ("ORB", "VG", "Z"), "ORB+VG+Z+RS": ("ORB", "VG", "Z", "RS"), "VG+Z": ("VG", "Z")}
    print("time-aware sim, flat n MNQ per leg; mean 24-month cash per account, 2018-21 | 2022-25")
    for bn, use in books.items():
        for n in (2, 3, 4):
            for ds in (10 ** 9, 600, 300):
                res = []
                for lo, hi in (("0", "2022"), ("2022", "9")):
                    cal = [d for d in cal_all if lo <= d < hi]
                    days = days_for(tr, cal, n, ds, use)
                    sz = lambda room, n=n: (float(n), 10 ** 9)
                    f1 = outcomes(days, sz, window=300, start_pnl=0.0, target=4000.0, consistency=False)
                    rp = outcomes(days, sz, window=300, start_pnl=2000.0, target=4000.0, consistency=False, locked=100.0)
                    res.append(life(f1, rp))
                lab = "none" if ds > 10 ** 6 else f"-${ds}"
                print(f"   {bn:<12} flat {n}  day stop {lab:>6}   ${res[0]:8,.0f} | ${res[1]:8,.0f}")


if __name__ == "__main__":
    main()
