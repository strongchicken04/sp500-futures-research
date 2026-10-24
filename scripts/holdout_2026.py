"""True holdout: 2026 year to date (never seen by any test; exports *26 run on
2026-10-24 from 2025-01-01 for warm-up). Rules exactly as in the plan:
  funded legs VG (Lucid 2), Z (Lucid 6), RS (Lucid 8, +/-1.25%), V10 (VWAP side
  10:00, +0.30/-0.50) with the vol gate; ORB not in the plan
  eval sprints RS (0.20/0.30), 09:31 trend (0.25/0.40), VWAP10 (0.25/0.40)
Reports per leg $ per MNQ trade and t, the book at 4 MNQ (total, worst
drawdown of closed daily P&L), the funded account walked from each start day
(first payout reached?), and the sprints' resolved win rate vs random.
Usage: holdout_2026.py DATA_DIR
"""
from __future__ import annotations

import math
import statistics as st
import sys

sys.path.insert(0, "scripts")
import funded_model as M  # noqa: E402
import level_lab as L  # noqa: E402
import mtm_check as C  # noqa: E402
from score_multi_feature import parse as parse_mf, first_signals, LEVELS as ML  # noqa: E402
from score_cond_bracket import parse, LEVELS as CL  # noqa: E402
from b_sprint_lab import trend_map, sgn  # noqa: E402
from vside_plateau import vside  # noqa: E402

LO = "2026"


def tstat(v):
    sd = st.pstdev(v) if len(v) > 2 else 0
    return st.mean(v) / sd * math.sqrt(len(v)) if sd else 0.0


def resolved(rows, ti, si, lv):
    h = s_ = 0
    for r, s in rows:
        fav, adv = (r["up"], r["dn"]) if s == 1 else (r["dn"], r["up"])
        t, sl = fav[lv.index(ti)], adv[lv.index(si)]
        if t >= 0 and (sl < 0 or t < sl):
            h += 1
        elif sl >= 0:
            s_ += 1
    return h, s_


def main():
    data = sys.argv[1]
    C.PANEL_LEGS = {"V10": vside(5, 0.0030, 0.0050)}
    L.NAMES = ("B2_26",)
    rvo = {}
    for f in ("LSVWAP26", "LSNOISE26"):
        for raw in open(f"{data}/{f}_tags.txt"):
            p = raw.strip().split(",")
            if p[0] == "L" and len(p) >= 10 and int(p[9]) > 0:
                rvo[f"{p[2][:4]}-{p[2][4:6]}-{p[2][6:]}"] = int(p[9]) / 1000.0
    tr, by = C.trades(data, "26", lambda d: 0 < rvo.get(d, 9.0) < 0.30, None)
    tr = [t for t in tr if t[0] >= LO]
    cal = sorted(d for d in {r["date"] for r in parse([f"{data}/CBA26_tags.txt"])} if d >= LO)
    print(f"2026 holdout: {cal[0]} .. {cal[-1]}, {len(cal)} RTH days; vol-gated days {sum(1 for d in cal if not 0 < rvo.get(d, 9.0) < 0.30)}")
    for k in ("VG", "Z", "RS", "V10"):
        v = [t[3] for t in tr if t[4] == k]
        if v:
            print(f"   {k:<4} n {len(v):3d}  ${st.mean(v):+7.2f} per MNQ trade  t {tstat(v):+4.1f}  total at 4 MNQ ${sum(v) * 4:+8,.0f}")
    T = {}
    for t in tr:
        T.setdefault(t[0], []).append(t)
    for name, mix in (("VG+Z+RS+V10 at 4", {"VG": 4, "Z": 4, "RS": 4, "V10": 4}), ("VG+Z+RS at 4", {"VG": 4, "Z": 4, "RS": 4}),
                      ("VG+Z+RS at 3", {"VG": 3, "Z": 3, "RS": 3})):
        dl = [C.day_seq(T.get(d, []), by[d]["bars"] if d in by else None, mix, None, True) for d in cal]
        daily = [sum(x) for x in dl]
        eq, peak, mdd = 0.0, 0.0, 0.0
        for x in daily:
            eq += x
            peak = max(peak, eq)
            mdd = min(mdd, eq - peak)
        fp = [r for r in (M.first_payout(dl[s:], lambda d, s: d) for s in range(max(1, len(dl) - 60))) if r]
        print(f"   book {name:<18} total ${sum(daily):+8,.0f}, worst closed drawdown ${mdd:,.0f}, "
              f"funded start on each day (>= 60 days left): first payout {sum(r for r, _ in fp)}/{len(fp)}, "
              f"bust {sum(1 for r, _ in fp if not r)}")
    rs = first_signals(parse_mf(f"{data}/MFEAT26_tags.txt"), lambda r: 1 if (r["rs"] > 0.0015 and r["vwapd"] > 0) else
                       (-1 if (r["rs"] < -0.0015 and r["vwapd"] < 0) else 0))
    R = {}
    for r in parse([f"{data}/CBA26_tags.txt"]):
        R.setdefault(r["type"], []).append(r)
    tm = trend_map(R["T931"])
    sprints = {"RS 0.20/0.30": ([v for d, v in rs.items() if d >= LO], 20, 30, ML),
               "09:31 0.25/0.40": ([(r, tm[r["date"]]) for r in R["T931"] if r["date"] >= LO and tm.get(r["date"])], 25, 40, CL),
               "VWAP10 0.25/0.40": ([(r, sgn(r["e"] - r["vwap"])) for r in R["T1000"] if r["date"] >= LO and sgn(r["e"] - r["vwap"])], 25, 40, CL)}
    for name, (rows, tp, sp, lv) in sprints.items():
        h, s_ = resolved(rows, tp, sp, lv)
        print(f"   sprint {name:<17} signals {len(rows):3d}, resolved {h + s_}, win {h / max(1, h + s_) * 100:5.1f}% vs random {sp / (tp + sp) * 100:4.1f}%")


if __name__ == "__main__":
    main()
