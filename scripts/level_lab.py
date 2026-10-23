"""Level lab: simple volume-profile / key-level day-trading rules on NQ 5-minute
RTH bars (BARS5A / BARS5B exports, see strategy/quantconnect/bars5_exporter.py).

Rules (fixed before looking at results, 2026-10-23 day shift):
  VA80   Dalton 80% rule: open outside the prior value area; two consecutive
         30-min periods close inside it -> trade toward the opposite edge.
         Stop: the entry-side edge +/- buf x VA width (buf 0.15/0.25/0.35);
         target: the opposite edge; else flat 15:55. Signal by 13:30.
  OUTV   open outside value and the first 30 minutes stay outside (low >
         prior VAH, or high < prior VAL) -> go with it at 10:00; stop at the
         VA edge (or at the prior POC); flat 15:55.
  POC    first touch of the prior POC after opening above it -> long at the
         POC (mirror short); stop 0.20/0.25/0.30%, target 2x stop; flat 15:55;
         touches until 14:00.
  IB     initial balance 09:30-10:30; first 5-min close beyond it -> go with it;
         stop at the IB middle, target IB edge + 0.5/1.0/1.5 x IB range; flat 15:55.
  PDBRK  first 5-min close beyond the prior day high/low (opened inside) -> go
         with it; stop 0.10/0.15/0.20% back inside the level; flat 15:55.
  PDSWP  price trades beyond the prior day high/low, then a 5-min bar closes
         back inside -> fade it; stop 2 pt beyond the day extreme so far;
         target the prior POC (if on the right side) else flat 15:55.
  ONSWP  the same with the overnight high/low (signals 09:35-12:00).
Second group (also fixed before results):
  NPOC   naked POC: the most recent POC of the last 5 sessions that no later
         session traded through; first touch today -> trade toward it as POC
         (stop 0.25%, target 0.50%).
  ODRIVE open drive: first 30 minutes never trade more than 0.05% against the
         open and close >= 0.15% beyond it -> go with it at 10:00, stop at the
         open -/+ 0.05%, flat 15:55.
  NARROW prior VA width in the lowest third of the previous 20 sessions; first
         5-min close outside the prior VA from 10:00 -> go with it, stop at the
         VA middle, flat 15:55. WIDE = same rule on the top third (control).

Fills: entry at the signal bar's close (POC: at the level, the touching bar
is checked for the stop); tracking from the next bar; a bar touching stop and
target = stop; stops fill at the worse of stop and the bar open. Costs per
MNQ: 0.75 pt + 0.25 pt on stops. Sessions where the contract changed since the
prior session are skipped (levels from another contract).

Usage: level_lab.py [DATA_DIR]   (needs BARS5A_tags.txt, BARS5B_tags.txt)
"""
from __future__ import annotations

import math
import os
import statistics as st
import sys
from collections import defaultdict

EOD = 76          # bar ending 15:55
LAST_ENTRY = 74   # bar ending 15:45


def load(data_dir):
    days = {}
    bars = defaultdict(dict)
    for nm in ("BARS5A", "BARS5B"):
        p = os.path.join(data_dir, f"{nm}_tags.txt")
        if not os.path.exists(p):
            continue
        for raw in open(p):
            f = raw.strip().split(",")
            if f[0] == "H" and len(f) >= 12:
                days[f[1]] = {"exp": f[2], "onh": float(f[3]), "onl": float(f[4]), "onpoc": float(f[5]),
                              "poc": float(f[7]), "vah": float(f[8]), "val": float(f[9]), "base": float(f[11])}
            elif f[0] == "B" and len(f) >= 4:
                bars[f[1]][int(f[2])] = f[3]
    out = []
    for d in sorted(days):
        h = days[d]
        if d not in bars:
            continue
        b = []
        for k in sorted(bars[d]):
            for s in bars[d][k].split("/"):
                o, hi, lo, c, v = (int(x) for x in s.split(":"))
                b.append((h["base"] + o / 4, h["base"] + hi / 4, h["base"] + lo / 4, h["base"] + c / 4, v))
        if len(b) < EOD + 1:
            continue          # half days
        h["date"] = f"{d[:4]}-{d[4:6]}-{d[6:]}"
        h["bars"] = b
        h["hi"] = max(x[1] for x in b)
        h["lo"] = min(x[2] for x in b)
        out.append(h)
    return out


def run(bars, i, d, e, stop, tgt=None, check_entry_bar=False):
    """Trade entered at bar i (price e). Returns net points per MNQ."""
    rng = range(i if check_entry_bar else i + 1, EOD + 1)
    for k in rng:
        o, h, l, c, _ = bars[k]
        first = check_entry_bar and k == i
        if (d == 1 and l <= stop) or (d == -1 and h >= stop):
            x = stop if first else (min(stop, o) if d == 1 else max(stop, o))
            return d * (x - e) - 1.0, "SL"
        if not first and tgt is not None and ((d == 1 and h >= tgt) or (d == -1 and l <= tgt)):
            return d * (tgt - e) - 0.75, "TP"
        if k == EOD:
            return d * (c - e) - 0.75, "EOD"
    return d * (bars[EOD][3] - e) - 0.75, "EOD"


def periods30(bars):
    return [(max(b[1] for b in bars[j:j + 6]), min(b[2] for b in bars[j:j + 6]), bars[j + 5][3], j + 5)
            for j in range(0, 78 - 5, 6)]


def va80(day, prev, buf):
    vah, val = prev["vah"], prev["val"]
    w = vah - val
    o = day["bars"][0][0]
    if w <= 0 or val <= o <= vah:
        return None
    side = 1 if o > vah else -1
    p = periods30(day["bars"])
    for n in range(1, len(p)):
        if p[n][3] > 47:          # second period must close by 13:30
            break
        if val <= p[n - 1][2] <= vah and val <= p[n][2] <= vah:
            i = p[n][3]
            e = day["bars"][i][3]
            d = -side
            stop = vah + buf * w if side == 1 else val - buf * w
            tgt = val if side == 1 else vah
            return d, run(day["bars"], i, d, e, stop, tgt)
    return None


def outv(day, prev, stop_kind):
    b = day["bars"]
    vah, val, poc = prev["vah"], prev["val"], prev["poc"]
    hi, lo = max(x[1] for x in b[:6]), min(x[2] for x in b[:6])
    if lo > vah:
        d, stop = 1, (vah if stop_kind == "edge" else poc)
    elif hi < val:
        d, stop = -1, (val if stop_kind == "edge" else poc)
    else:
        return None
    return d, run(b, 5, d, b[5][3], stop)


def poc_touch(day, prev, sp):
    b = day["bars"]
    poc = prev["poc"]
    o = b[0][0]
    if o == poc:
        return None
    d = 1 if o > poc else -1
    for i in range(0, 54):        # touches by 14:00
        if (d == 1 and b[i][2] <= poc) or (d == -1 and b[i][1] >= poc):
            e = min(poc, b[i][0]) if d == 1 else max(poc, b[i][0])
            stop = e * (1 - d * sp)
            tgt = e * (1 + d * 2 * sp)
            return d, run(b, i, d, e, stop, tgt, check_entry_bar=True)
    return None


def ib(day, prev, ext):
    b = day["bars"]
    ibh, ibl = max(x[1] for x in b[:12]), min(x[2] for x in b[:12])
    r = ibh - ibl
    for i in range(12, LAST_ENTRY + 1):
        c = b[i][3]
        if c > ibh or c < ibl:
            d = 1 if c > ibh else -1
            tgt = ibh + ext * r if d == 1 else ibl - ext * r
            return d, run(b, i, d, c, (ibh + ibl) / 2, tgt)
    return None


def pdbrk(day, prev, sp):
    b = day["bars"]
    pdh, pdl = prev["hi"], prev["lo"]
    if not (pdl < b[0][0] < pdh):
        return None
    for i in range(0, LAST_ENTRY + 1):
        c = b[i][3]
        if c > pdh or c < pdl:
            d = 1 if c > pdh else -1
            lvl = pdh if d == 1 else pdl
            return d, run(b, i, d, c, lvl * (1 - d * sp))
    return None


def sweep(day, prev, hi_lvl, lo_lvl, last):
    b = day["bars"]
    if not (lo_lvl < b[0][0] < hi_lvl):
        return None
    above = below = False
    ext_hi, ext_lo = -1e18, 1e18
    for i in range(0, last + 1):
        o, h, l, c, _ = b[i]
        ext_hi, ext_lo = max(ext_hi, h), min(ext_lo, l)
        above = above or h > hi_lvl
        below = below or l < lo_lvl
        if above and c < hi_lvl:
            tgt = prev["poc"] if prev["poc"] < c else None
            return -1, run(b, i, -1, c, ext_hi + 2.0, tgt)
        if below and c > lo_lvl:
            tgt = prev["poc"] if prev["poc"] > c else None
            return 1, run(b, i, 1, c, ext_lo - 2.0, tgt)
    return None


def touch(day, lvl, sp, last=54):
    b = day["bars"]
    o = b[0][0]
    if o == lvl:
        return None
    d = 1 if o > lvl else -1
    for i in range(0, last):
        if (d == 1 and b[i][2] <= lvl) or (d == -1 and b[i][1] >= lvl):
            e = min(lvl, b[i][0]) if d == 1 else max(lvl, b[i][0])
            return d, run(b, i, d, e, e * (1 - d * sp), e * (1 + d * 2 * sp), check_entry_bar=True)
    return None


def odrive(day, prev):
    b = day["bars"]
    o = b[0][0]
    hi, lo, c = max(x[1] for x in b[:6]), min(x[2] for x in b[:6]), b[5][3]
    if lo >= o * (1 - 0.0005) and c >= o * 1.0015:
        return 1, run(b, 5, 1, c, o * (1 - 0.0005))
    if hi <= o * (1 + 0.0005) and c <= o * (1 - 0.0015):
        return -1, run(b, 5, -1, c, o * (1 + 0.0005))
    return None


def va_break(day, prev):
    b = day["bars"]
    vah, val = prev["vah"], prev["val"]
    for i in range(5, LAST_ENTRY + 1):
        c = b[i][3]
        if c > vah or c < val:
            d = 1 if c > vah else -1
            return d, run(b, i, d, c, (vah + val) / 2)
    return None


def annotate(days):
    """Adds npoc (naked POC of the last 5 sessions, as known before the session)
    and the prior VA width tercile vs the previous 20 sessions."""
    for n, day in enumerate(days):
        day["npoc"] = None
        for j in range(n - 1, max(-1, n - 6), -1):
            if days[j]["exp"] != day["exp"]:
                break
            p = days[j]["poc"]
            if j == n - 1:             # the prior POC itself is the POC rule
                continue
            if all(not (days[k]["lo"] <= p <= days[k]["hi"]) for k in range(j + 1, n)):
                day["npoc"] = p
                break
        if n >= 21:
            ws = sorted(days[k]["vah"] - days[k]["val"] for k in range(n - 21, n - 1))
            w = days[n - 1]["vah"] - days[n - 1]["val"]
            day["vaw"] = "narrow" if w <= ws[len(ws) // 3] else "wide" if w >= ws[2 * len(ws) // 3] else "mid"
        else:
            day["vaw"] = None


def rules():
    R = {}
    for buf in (0.15, 0.25, 0.35):
        R[f"VA80 buf {buf}"] = lambda d, p, buf=buf: va80(d, p, buf)
    for k in ("edge", "poc"):
        R[f"OUTV stop {k}"] = lambda d, p, k=k: outv(d, p, k)
    for sp in (0.002, 0.0025, 0.003):
        R[f"POC stop {sp * 100:.2f}%"] = lambda d, p, sp=sp: poc_touch(d, p, sp)
    for ext in (0.5, 1.0, 1.5):
        R[f"IB ext {ext}"] = lambda d, p, ext=ext: ib(d, p, ext)
    for sp in (0.001, 0.0015, 0.002):
        R[f"PDBRK stop {sp * 100:.2f}%"] = lambda d, p, sp=sp: pdbrk(d, p, sp)
    R["PDSWP"] = lambda d, p: sweep(d, p, p["hi"], p["lo"], 54)
    R["ONSWP"] = lambda d, p: sweep(d, p, d["onh"], d["onl"], 29)
    R["NPOC"] = lambda d, p: touch(d, d["npoc"], 0.0025) if d["npoc"] else None
    R["ODRIVE"] = odrive
    R["NARROW"] = lambda d, p: va_break(d, p) if d["vaw"] == "narrow" else None
    R["WIDE"] = lambda d, p: va_break(d, p) if d["vaw"] == "wide" else None
    return R


def stat(v):
    if len(v) < 5:
        return f"n {len(v)}"
    sd = st.pstdev(v) or 1.0
    return f"{st.mean(v):+6.2f} pt t{st.mean(v) / sd * math.sqrt(len(v)):+4.1f} n{len(v):>4} WR {sum(x > 0 for x in v) / len(v) * 100:3.0f}%"


def trades(days, fn):
    out = []
    for prev, day in zip(days, days[1:]):
        if day["exp"] != prev["exp"]:
            continue
        r = fn(day, prev)
        if r:
            d, (pts, why) = r
            out.append({"date": day["date"], "d": d, "pts": pts, "why": why})
    return out


def main():
    data = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("BRAIN_DATA", "/tmp/brain_data")
    days = load(data)
    annotate(days)
    print(f"sessions {len(days)}: {days[0]['date']} .. {days[-1]['date']}")
    for lbl, i in (("09:35", 0), ("10:00", 5), ("10:35", 12)):
        v = [x["bars"][EOD][3] - x["bars"][i][3] for x in days]
        a = [y for x, y in zip(days, v) if x["date"] < "2022"]
        b = [y for x, y in zip(days, v) if x["date"] >= "2022"]
        print(f"baseline drift {lbl} close -> 15:55 (gross, long): {st.mean(a) if a else 0:+.2f} | {st.mean(b) if b else 0:+.2f} pt")
    print()
    for name, fn in rules().items():
        ts = trades(days, fn)
        a = [t["pts"] for t in ts if t["date"] < "2022"]
        b = [t["pts"] for t in ts if t["date"] >= "2022"]
        yrs = sorted({t["date"][:4] for t in ts})
        by = " ".join(f"{y[2:]}:{sum(t['pts'] for t in ts if t['date'][:4] == y):+.0f}" for y in yrs)
        lo = [t["pts"] for t in ts if t["d"] == 1]
        sh = [t["pts"] for t in ts if t["d"] == -1]
        print(f"{name:<18} 2018-21 {stat(a)} | 2022-25 {stat(b)}")
        print(f"{'':<18} long {stat(lo)} | short {stat(sh)}")
        print(f"{'':<18} years {by}\n")


if __name__ == "__main__":
    main()
