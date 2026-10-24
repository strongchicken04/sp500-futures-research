"""VWAP band leg (Lucid 2) with brackets in % of price (day shift 2026-10-24,
fixed before results). The live rule uses SL 25 / TP 100 POINTS: ~0.28% /
1.1% at NQ ~9,000 when it was tuned (2018-21), only ~0.09% / 0.35% at
today's 28,500. Rebuilt on the 5-min panel: 5-min close breaks out of the RTH
VWAP +/-0.20% band (previous close inside), first trade of the day, not on
Wednesday, entry at that close, exits from the next bar, flat 15:55, vol gate.
Variants (stop / target in % of entry):
  LIVE@today  0.088 / 0.35  (25 / 100 pt at 28,530)
  P25         0.25 / 1.00   (the tuned points expressed in %)
  P20         0.20 / 0.80      P30  0.30 / 1.20      P15  0.15 / 0.60
Per trade: $ per MNQ at today's price (gross % x 28,530 - 0.75 pt, 1.0 on
stops), four eras + 2026 holdout.
Usage: vg_pct.py DATA_DIR
"""
from __future__ import annotations

import datetime as dt
import math
import statistics as st
import sys

sys.path.insert(0, "scripts")
import level_lab as L  # noqa: E402
from rescore_all import rvol  # noqa: E402
from size_today import PRICE, rvmap  # noqa: E402

VARS = {"LIVE@today": (0.25 * 25 / PRICE * 4, 100 / PRICE), "P25": (0.0025, 0.0100), "P20": (0.0020, 0.0080),
        "P30": (0.0030, 0.0120), "P15": (0.0015, 0.0060)}
VARS["LIVE@today"] = (25 / PRICE, 100 / PRICE)
BAND = 0.0020


def vg(sp, tp):
    def make(days):
        def f(d, p):
            if dt.date.fromisoformat(d["date"]).weekday() == 2:
                return None
            b = d["bars"]
            vw = L.vwaps(b)
            for i in range(1, L.LAST_ENTRY + 1):
                up, dn = vw[i] * (1 + BAND), vw[i] * (1 - BAND)
                pin = vw[i - 1] * (1 - BAND) <= b[i - 1][3] <= vw[i - 1] * (1 + BAND)
                c = b[i][3]
                if pin and (c > up or c < dn):
                    s = 1 if c > up else -1
                    return s, L.run(b, i, s, c, c * (1 - s * sp), c * (1 + s * tp))
            return None
        return f
    return make


def main():
    data = sys.argv[1]
    reg = rvol()
    ro, r26 = rvmap(data, ("LSVWAP_OLD", "LSNOISE_OLD")), rvmap(data, ("LSVWAP26", "LSNOISE26"))
    sets = ((("B2_0A", "B2_0B"), lambda d: 0 < ro.get(d, 9.0) < 0.30, (("2010", "2014", "2010-13"), ("2014", "2018", "2014-17"))),
            (("BARS5A", "BARS5B"), lambda d: reg.get(d, 9.0) < 0.30, (("2018", "2022", "2018-21"), ("2022", "2026", "2022-25"))),
            (("B2_26",), lambda d: 0 < r26.get(d, 9.0) < 0.30, (("2026", "2027", "2026 H1"),)))
    print(f"$ per MNQ trade at NQ {PRICE:,.0f} (net), t-stat, n")
    rows = {k: [] for k in VARS}
    for names, gate, halves in sets:
        L.NAMES = names
        days = L.load(data)
        by = {d["date"]: d for d in days}
        for k, (sp, tp) in VARS.items():
            tr = [t for t in L.trades(days, vg(sp, tp)(days)) if gate(t["date"])]
            for lo, hi, lab in halves:
                v = []
                for t in tr:
                    if not lo <= t["date"] < hi:
                        continue
                    e = by[t["date"]]["bars"][(t["ehm"] - 575) // 5][3]
                    c = 1.0 if t["why"] == "SL" else 0.75
                    v.append(((t["pts"] + c) / e * PRICE - c) * 2.0)
                sd = st.pstdev(v) or 1.0
                rows[k].append(f"{lab} ${st.mean(v):+6.2f} t{st.mean(v) / sd * math.sqrt(len(v)):+4.1f} n{len(v)}")
    for k, r in rows.items():
        print(f"   {k:<11} " + " | ".join(r))


if __name__ == "__main__":
    main()
