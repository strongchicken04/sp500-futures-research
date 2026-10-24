"""Intraday drawdown with OPEN positions (night shift 2026-10-23/24, fixed
before results). funded_model checks the drawdown after each closed trade;
the real account fails when equity INCLUDING open P&L touches the line. Here
every open trade is marked at the adverse extreme (low for longs, high for
shorts) of each 5-minute bar that lies fully inside its holding time, using
the BARS5 panel (2018-25: BARS5A/B, 2010-17: B2_0A/B), all open trades at
their worst in the same bar (conservative). Days missing from the panel
(half days) keep the closed-trade check only.
Book: VG + Z + RS (+ OD) as funded_v2 / addon_v2. Variants flat 3, flat 4,
flat 4 + OD 4, flat 5; closed-only check vs open-P&L check. 2010-17
re-priced at today's NQ as funded_scaled_old.
Usage: mtm_check.py DATA_DIR
"""
from __future__ import annotations

import datetime as dt
import statistics as st
import sys

sys.path.insert(0, "scripts")
import funded_model as M  # noqa: E402
import level_lab as L  # noqa: E402
from mc_simple import nr4  # noqa: E402,F401
from rescore_all import rvol  # noqa: E402
from score_multi_feature import parse as parse_mf, first_signals, LEVELS  # noqa: E402
from rs_book import pts as rs_pts  # noqa: E402
from score_cond_bracket import parse  # noqa: E402

EODM = 955
V = {"flat 3": {"VG": 3, "Z": 3, "RS": 3}, "flat 4": {"VG": 4, "Z": 4, "RS": 4},
     "flat 4 + OD 4": {"VG": 4, "Z": 4, "RS": 4, "OD": 4}, "flat 5": {"VG": 5, "Z": 5, "RS": 5}}


RS_LEVEL = 125   # RS leg bracket in bp (rs_bracket.py varies it)
WITH_ORB = False  # orb_v2.py adds the live-spec ORB (O5) leg
UNGATED = set()   # legs traded without the vol gate (gate_v2.py)
PANEL_LEGS = {"OD": lambda days: (lambda d, p: L.odrive(d, p, 0.0005, 0.0015))}   # 5-min panel legs
MARK = "worst"    # "close": mark open trades at the bar close (lenient bound, mtm_close.py)


def trades(data, suffix, gate, pref):
    """(date, ehm, xhm, usd per MNQ, leg, dir); usd re-priced at pref if given (gross % x pref - cost)."""
    out = []
    files = (("LSVWAP" + suffix, "B5", "VG"), ("LSNOISE" + suffix, "NS", "Z"))
    if WITH_ORB:
        files += tuple((f, "O5", "ORB") for f in (("LSORB_OLD",) if suffix else ("LSORB_A", "LSORB_B")))
    for f, var, leg in files:
        for raw in open(f"{data}/{f}_tags.txt"):
            p = raw.strip().split(",")
            if p[0] != "L" or len(p) < 10 or p[1] != var:
                continue
            d, e, x = int(p[3]), float(p[5]), float(p[7])
            rv = int(p[9]) / 1000.0
            date = f"{p[2][:4]}-{p[2][4:6]}-{p[2][6:]}"
            if not (0 < rv < 0.30) and leg not in UNGATED:
                continue
            c = 1.0 if p[8] in ("SL", "STOP") else 0.75
            pts = d * (x - e) * (pref / e if pref else 1.0) - c
            out.append((date, int(p[4]), int(p[6]), pts * 2.0, leg, d))
    sig = first_signals(parse_mf(f"{data}/MFEAT{suffix}_tags.txt"), lambda r: 1 if (r["rs"] > 0.0015 and r["vwapd"] > 0) else
                        (-1 if (r["rs"] < -0.0015 and r["vwapd"] < 0) else 0))
    ti = si = LEVELS.index(RS_LEVEL)
    for d, (r, s) in sig.items():
        if not gate(d) and "RS" not in UNGATED:
            continue
        fav, adv = (r["up"], r["dn"]) if s == 1 else (r["dn"], r["up"])
        hits = [k for k in (fav[ti], adv[si]) if k >= 0]
        x = min(EODM, r["hm"] + min(hits)) if hits else EODM
        pts = rs_pts(r, s, ti, si)
        if pref:
            c = 1.0 if pts < -(RS_LEVEL / 1e4 - 0.0001) * r["e"] else 0.75
            pts = (pts + c) / r["e"] * pref - c
        out.append((d, r["hm"], x, pts * 2.0, "RS", s))
    days = L.load(data)
    by = {d["date"]: d for d in days}
    for leg, make in PANEL_LEGS.items():
        rebate = 0.25 if leg == "SB" else 0.0      # limit entry: 0.5 pt instead of 0.75
        for t in L.trades(days, make(days)):
            if not gate(t["date"]):
                continue
            usd = (t["pts"] + rebate) * 2.0
            if pref:
                e = by[t["date"]]["bars"][(t["ehm"] - 575) // 5][3]
                c = (1.0 if t["why"] == "SL" else 0.75) - rebate
                usd = ((t["pts"] + rebate + c) / e * pref - c) * 2.0
            out.append((t["date"], t["ehm"], t["xhm"], usd, leg, t["d"]))
    out = [t for t in out if not (dt.date.fromisoformat(t[0]).weekday() == 2 and t[4] in ("VG", "ORB"))]
    return out, by


def day_seq(tr, bars, mix, f, mtm):
    """Increments whose running sum traces the day's equity (closed + open)."""
    tr = [t for t in tr if t[4] in mix]
    ev = [(t[2], 1, t[3] * mix[t[4]]) for t in tr]        # exits
    if mtm and bars:
        for k in range(len(bars)):
            t0, t1 = 570 + 5 * k, 575 + 5 * k
            dip = 0.0
            for d, eh, xh, usd, leg, s in tr:
                if eh <= t0 and t1 < xh:
                    ie = (eh - 575) // 5
                    if 0 <= ie < len(bars):
                        ent = bars[ie][3]
                        adv = bars[k][3] if MARK == "close" else (bars[k][2] if s == 1 else bars[k][1])
                        dip += min(0.0, s * (adv - ent)) * 2.0 * mix[leg] * (f(ent) if f else 1.0)
            if dip < 0:
                ev.append((t1, 0, dip))
                ev.append((t1, 0, -dip))
    ev.sort(key=lambda e: (e[0], e[1]))
    return [e[2] for e in ev]


def run(lab, cal, tr, by, f):
    T = {}
    for t in tr:
        T.setdefault(t[0], []).append(t)
    paths = M.bootstrap(len(cal), 3000, seed=31)
    print(f"--- {lab}: 24-month cash per seat | first payout  (closed-trade check -> with open P&L)")
    for name, mix in V.items():
        cells = []
        for mtm in (False, True):
            dl = [day_seq(T.get(d, []), by[d]["bars"] if d in by else None, mix, f, mtm) for d in cal]
            cash = st.mean(M.run_path([dl[i] for i in p], lambda d, s: d) for p in paths)
            fp = [x for x in (M.first_payout(dl[s:], lambda d, s: d) for s in range(len(dl) - 250)) if x]
            cells.append(f"${cash:7,.0f} {sum(r for r, _ in fp) / len(fp) * 100:4.1f}%")
        print(f"   {name:<14} " + "  ->  ".join(cells))


def main():
    data = sys.argv[1]
    reg = rvol()
    tr, by = trades(data, "", lambda d: reg.get(d, 9.0) < 0.30, None)
    full = sorted({r["date"] for r in parse([f"{data}/CBA_tags.txt"])})
    print(f"panel coverage 2018-25: {sum(d in by for d in full)} of {len(full)} days")
    for lo, hi, lab in (("2018", "2022", "2018-21"), ("2022", "2026", "2022-25")):
        run(lab, [d for d in full if lo <= d < hi], tr, by, None)
    pref = st.mean(float(p.split(",")[5]) for p in open(f"{data}/LSNOISE_tags.txt") if p.startswith("L,NS,2022") or p.startswith("L,NS,2023")
                   or p.startswith("L,NS,2024") or p.startswith("L,NS,2025"))
    L.NAMES = ("B2_0A", "B2_0B")
    rvo = {}
    for f in ("LSVWAP_OLD", "LSNOISE_OLD"):
        for raw in open(f"{data}/{f}_tags.txt"):
            p = raw.strip().split(",")
            if p[0] == "L" and len(p) >= 10 and int(p[9]) > 0:
                rvo[f"{p[2][:4]}-{p[2][4:6]}-{p[2][6:]}"] = int(p[9]) / 1000.0
    tr, by = trades(data, "_OLD", lambda d: 0 < rvo.get(d, 9.0) < 0.30, pref)
    full = sorted({r["date"] for r in parse([f"{data}/CBA_OLD_tags.txt"])})
    print(f"reference price {pref:,.0f}; panel coverage 2010-17: {sum(d in by for d in full)} of {len(full)} days")
    for lo, hi, lab in (("2010", "2014", "2010-13 (today's price)"), ("2014", "2018", "2014-17 (today's price)")):
        run(lab, [d for d in full if lo <= d < hi], tr, by, lambda e: pref / e)


if __name__ == "__main__":
    main()
