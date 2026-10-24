"""Timing robustness of noise momentum (night 2026-10-24/25, guardrail 6c):
Lucid 6 rebuilt on the 5-min panel with decisions at the closes of the bars
ending :00/:30 (live), shifted -5 min (:55/:25) and +5 min (:05/:35).
sigma(t) = mean over the last 14 sessions of |close(t) / open - 1| at the same
bar; upper = max(open, prior close) x (1 + sigma), lower = min(...) x (1 - sigma);
long above upper, short below lower; a long exits at a decision when the
close < max(upper, VWAP) (short mirrored); opposite signal reverses; hard stop
0.50% from entry checked on every bar after entry (fill at the worse of stop
and open); flat 15:55; vol gate as the live leg; costs 0.75 pt per trade +0.25
on stops. Re-priced at today's NQ; four eras + 2026. The shift-0 version is
compared with the live-spec export as a sanity check.
Usage: z_timing.py DATA_DIR
"""
from __future__ import annotations

import math
import statistics as st
import sys

sys.path.insert(0, "scripts")
import level_lab as L  # noqa: E402
from rescore_all import rvol  # noqa: E402
from size_today import PRICE, rvmap  # noqa: E402
from score_live_spec import parse as parse_ls  # noqa: E402

EOD = 76


def noise_trades(days, shift, gate):
    dec = [k + shift for k in range(5, 72, 6)]           # bars ending 10:00 .. 15:30 (+shift bars)
    out = []
    hist = []                                            # per day: list of |c/o - 1| per bar
    prev_close = None
    for d in days:
        b = d["bars"]
        o = b[0][0]
        if len(hist) >= 14 and prev_close and gate(d["date"]):
            vw = L.vwaps(b)
            pos, e, ei = 0, 0.0, 0
            for k in range(1, EOD + 1):
                bo, bh, bl, bc, _ = b[k]
                if pos:
                    stop = e * (1 - pos * 0.005)
                    if (pos == 1 and bl <= stop) or (pos == -1 and bh >= stop):
                        x = min(stop, bo) if pos == 1 else max(stop, bo)
                        out.append((d["date"], pos, e, x, 1.0, ei, k))
                        pos = 0
                        continue
                if k in dec:
                    sig = st.mean(h[k] for h in hist[-14:])
                    up, dn = max(o, prev_close) * (1 + sig), min(o, prev_close) * (1 - sig)
                    want = 1 if bc > up else -1 if bc < dn else 0
                    if pos == 1 and (bc < max(up, vw[k]) or want == -1):
                        out.append((d["date"], pos, e, bc, 0.75, ei, k)); pos = 0
                    elif pos == -1 and (bc > min(dn, vw[k]) or want == 1):
                        out.append((d["date"], pos, e, bc, 0.75, ei, k)); pos = 0
                    if not pos and want:
                        pos, e, ei = want, bc, k
                if k == EOD and pos:
                    out.append((d["date"], pos, e, bc, 0.75, ei, k)); pos = 0
        hist.append([abs(x[3] / o - 1) for x in b])
        prev_close = b[EOD][3]
    return out


def main():
    data = sys.argv[1]
    reg = rvol()
    ro, r26 = rvmap(data, ("LSVWAP_OLD", "LSNOISE_OLD")), rvmap(data, ("LSVWAP26", "LSNOISE26"))
    sets = ((("B2_0A", "B2_0B"), lambda d: 0 < ro.get(d, 9.0) < 0.30, (("2010", "2014", "2010-13"), ("2014", "2018", "2014-17"))),
            (("BARS5A", "BARS5B"), lambda d: reg.get(d, 9.0) < 0.30, (("2018", "2022", "2018-21"), ("2022", "2025", "2022-24"), ("2025", "2026", "2025"))),
            (("B2_26",), lambda d: 0 < r26.get(d, 9.0) < 0.30, (("2026", "2027", "2026 H1"),)))
    live = parse_ls([f"{data}/LSNOISE_tags.txt"])["NS"]
    print(f"noise momentum on the 5-min panel, $ per MNQ trade at NQ {PRICE:,.0f} (net), t, n")
    for names, gate, halves in sets:
        L.NAMES = names
        days = L.load(data)
        for shift, lab0 in ((-1, "-5 min"), (0, "live :00/:30"), (1, "+5 min")):
            tr = noise_trades(days, shift, gate)
            cells = []
            for lo, hi, lab in halves:
                v = [((s * (x - e)) / e * PRICE - c) * 2.0 for dd, s, e, x, c, ei, xi in tr if lo <= dd < hi]
                cells.append(f"{lab} ${st.mean(v):+6.2f} t{st.mean(v) / (st.pstdev(v) or 1) * math.sqrt(len(v)):+4.1f} n{len(v)}" if v else f"{lab} n0")
            print(f"   {lab0:<13} " + " | ".join(cells))
        if names[0] == "BARS5A":
            tr = noise_trades(days, 0, gate)
            pv = {}
            for dd, s, e, x, c, ei, xi in tr:
                pv[dd] = pv.get(dd, 0.0) + s * (x - e) - c
            lv = {}
            for t in live:
                if 0 < t["rv"] < 0.30:
                    lv[t["date"]] = lv.get(t["date"], 0.0) + t["pts"]
            common = sorted(set(pv) & set(lv))
            a, b = [pv[d] for d in common], [lv[d] for d in common]
            ma, mb = st.mean(a), st.mean(b)
            cor = sum((x - ma) * (y - mb) for x, y in zip(a, b)) / math.sqrt(sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b))
            print(f"   sanity 2018-25: panel vs live-spec daily pts correlation {cor:.2f} on {len(common)} common days; days only panel {len(set(pv) - set(lv))}, only live {len(set(lv) - set(pv))}")


if __name__ == "__main__":
    main()
