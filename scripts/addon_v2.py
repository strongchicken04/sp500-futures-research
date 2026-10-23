"""Book add-ons on the corrected funded model (night shift 2026-10-23/24,
fixed before results). Open drive (OD: first 30 min one-way, enter 10:00) and
NR4 break were rejected as book legs on the old model ("more busts than
profit"); funded_model keeps the profit above +$4,000 and favours more size,
so re-test: base = no-ORB book at flat 4 (new recommendation) and at flat 3,
plus OD and/or NR4 at the same size, gated (prior-day rv20 < 0.30) as tested.
2018-21 / 2022-25 in real dollars; 2010-13 / 2014-17 re-priced at today's NQ
(gross % per trade, today's costs; as funded_scaled_old).
Usage: addon_v2.py DATA_DIR
"""
from __future__ import annotations

import statistics as st
import sys

sys.path.insert(0, "scripts")
import funded_model as M  # noqa: E402
import gate_check as G  # noqa: E402
import level_lab as L  # noqa: E402
import ict_lab as I  # noqa: E402
import funded_scaled_old as O  # noqa: E402
from mc_runs import sized  # noqa: E402
from mc_simple import nr4  # noqa: E402
from rescore_all import rvol  # noqa: E402
from score_cond_bracket import parse  # noqa: E402


def extra_legs(days, gate, pref=None):
    """OD and NR4 trades (date, ehm, xhm, usd per MNQ, leg); re-priced at pref if given."""
    by = {d["date"]: d for d in days}
    out = []
    for leg, fn in (("OD", lambda d, p: L.odrive(d, p, 0.0005, 0.0015)), ("NR", nr4(days))):
        for t in L.trades(days, fn):
            if not gate(t["date"]):
                continue
            usd = t["pts"] * 2.0
            if pref:
                i = (t["ehm"] - 575) // 5
                e = by[t["date"]]["bars"][i][3]
                c = 1.0 if t["why"] == "SL" else 0.75
                usd = ((t["pts"] + c) / e * pref - c) * 2.0
            out.append((t["date"], t["ehm"], t["xhm"], usd, leg))
    return out


def run(lab, cal, legs_one, variants):
    by = {}
    for t in legs_one:
        by.setdefault(t[0], []).append(t)
    days = [{k: [] for k in ("VG", "Z", "RS", "OD", "NR")} for _ in cal]
    seq = []
    for d in cal:
        seq.append(sorted(by.get(d, []), key=lambda t: t[2]))
    paths = M.bootstrap(len(cal), 4000, seed=99)
    print(f"--- {lab}")
    base = None
    for name, mix in variants.items():
        dl = [[t[3] * mix[t[4]] for t in s if t[4] in mix] for s in seq]
        fn = lambda d, s: d
        cash = [M.run_path([dl[i] for i in p], fn) for p in paths]
        fp = [x for x in (M.first_payout(dl[s:], fn) for s in range(len(dl) - 250)) if x]
        base = base or cash
        dd = [x - y for x, y in zip(cash, base)]
        print(f"   {name:<22} mean ${st.mean(cash):7,.0f} vs flat 4 {st.mean(dd):+7,.0f} (+/- {1.96 * st.pstdev(dd) / len(dd) ** 0.5:,.0f}) "
              f"better/worse {sum(x > 0 for x in dd) / len(dd) * 100:3.0f}/{sum(x < 0 for x in dd) / len(dd) * 100:3.0f}% | "
              f"first payout {sum(r for r, _ in fp) / len(fp) * 100:4.1f}%")


def main():
    data = sys.argv[1]
    b4 = {"VG": 4, "Z": 4, "RS": 4}
    V = {"flat 4": b4, "flat 4 + OD 4": dict(b4, OD=4), "flat 4 + NR4 4": dict(b4, NR=4), "flat 4 + OD + NR4": dict(b4, OD=4, NR=4),
         "flat 3": {"VG": 3, "Z": 3, "RS": 3}, "flat 3 + OD 3": {"VG": 3, "Z": 3, "RS": 3, "OD": 3}}
    reg = rvol()
    new = sized(G.build(data, set()), {"VG": 1, "Z": 1, "RS": 1})
    new += extra_legs(I.load(data), lambda d: reg.get(d, 9.0) < 0.30)
    full = sorted({r["date"] for r in parse([f"{data}/CBA_tags.txt"])})
    for lo, hi, lab in (("2018", "2022", "2018-21"), ("2022", "2026", "2022-25")):
        run(lab, [d for d in full if lo <= d < hi], new, V)
    pref = st.mean(t["e"] for t in O.ls_rows(f"{data}/LSNOISE_tags.txt", "NS") if t["date"] >= "2022")
    old, gated = O.legs(data, "_OLD")
    old1 = [(d, eh, xh, (ret * pref - c) * 2.0, leg) for d, eh, xh, ret, c, leg, e in old if leg != "ORB" and gated(d)]
    L.NAMES = ("B2_0A", "B2_0B")
    old1 += extra_legs(L.load(data), gated, pref)
    full = sorted({r["date"] for r in parse([f"{data}/CBA_OLD_tags.txt"])})
    for lo, hi, lab in (("2010", "2014", "2010-13 (today's price)"), ("2014", "2018", "2014-17 (today's price)")):
        run(lab, [d for d in full if lo <= d < hi], old1, V)


if __name__ == "__main__":
    main()
