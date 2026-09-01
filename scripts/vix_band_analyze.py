#!/usr/bin/env python3
"""Analyze VIX-implied 1-sigma band hit rate on NQ.

Vstup: JSON pole zaznamu z QC backtestu vix_band_exporter.py
  [{"date": "2018-01-04", "nq_open": 6600.0, "nq_high": 6620.0,
    "nq_low": 6580.0, "nq_close": 6610.0, "vix_prev": 9.5}, ...]

Model:
  denni sigma (%) = vix_prev / sqrt(252)   ~= vix_prev / 15.874
  pasmo (b)       = nq_open * denni_sigma / 100
  upper           = nq_open + pasmo
  lower           = nq_open - pasmo
  stayed_inside   = (nq_high <= upper) AND (nq_low >= lower)
  closed_inside   = (lower <= nq_close <= upper)

Vysledek: % dni, kdy cely intraday range zustal uvnitr, plus rozklad
po letech, po VIX kvintilech a srovnani s "close inside" (endpoint).
"""
import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

SQRT252 = math.sqrt(252.0)   # ~15.874


def load(path):
    rows = json.loads(Path(path).read_text())
    out = []
    for r in rows:
        try:
            o = float(r["nq_open"]); h = float(r["nq_high"])
            lo = float(r["nq_low"]); c = float(r["nq_close"])
            v = float(r["vix_prev"])
            if o > 0 and v > 0 and h >= lo:
                out.append((r["date"], o, h, lo, c, v))
        except (KeyError, ValueError, TypeError):
            continue
    return out


def analyze(rows):
    n = len(rows)
    stayed = 0; closed_in = 0
    breach_up = 0; breach_dn = 0
    per_year = defaultdict(lambda: [0, 0])         # [n, stayed]
    per_vix_q = defaultdict(lambda: [0, 0])
    band_widths_bps = []
    excess_by_stayed = {True: [], False: []}       # (range - band)/band, jak moc premrsklo

    vixs = sorted(r[5] for r in rows)
    # kvintily podle historickeho rozdeleni vstupu VIX
    qs = [vixs[int(k * n / 5)] for k in range(1, 5)]

    def vix_bucket(v):
        for i, q in enumerate(qs):
            if v <= q:
                return i
        return 4

    for date, o, h, lo, c, v in rows:
        year = date[:4]
        sigma_pct = v / SQRT252            # napr. VIX 20 -> 1.26 %
        band = o * sigma_pct / 100.0
        upper = o + band
        lower = o - band
        s = (h <= upper) and (lo >= lower)
        ci = (lower <= c <= upper)
        stayed += 1 if s else 0
        closed_in += 1 if ci else 0
        breach_up += 1 if h > upper else 0
        breach_dn += 1 if lo < lower else 0
        per_year[year][0] += 1
        per_year[year][1] += 1 if s else 0
        b = vix_bucket(v)
        per_vix_q[b][0] += 1
        per_vix_q[b][1] += 1 if s else 0
        band_widths_bps.append(sigma_pct * 100.0)  # v bps
        actual_range = h - lo
        excess_by_stayed[s].append((actual_range - 2 * band) / (2 * band))

    return dict(
        n=n,
        stayed_pct=100.0 * stayed / n if n else 0.0,
        closed_in_pct=100.0 * closed_in / n if n else 0.0,
        breach_up_pct=100.0 * breach_up / n if n else 0.0,
        breach_dn_pct=100.0 * breach_dn / n if n else 0.0,
        per_year=[(y, per_year[y][0], per_year[y][1],
                   100.0 * per_year[y][1] / per_year[y][0]) for y in sorted(per_year)],
        per_vix_q=[(i, qs[i - 1] if i > 0 else float("-inf"),
                    qs[i] if i < 4 else float("inf"),
                    per_vix_q[i][0], per_vix_q[i][1],
                    100.0 * per_vix_q[i][1] / per_vix_q[i][0])
                   for i in range(5)],
        avg_band_bps=sum(band_widths_bps) / n if n else 0.0,
    )


def fmt(a):
    lines = []
    lines.append(f"n = {a['n']} dni")
    lines.append(f"stayed inside band (high<=upper AND low>=lower): "
                 f"{a['stayed_pct']:.1f} %")
    lines.append(f"closed inside (endpoint):                       "
                 f"{a['closed_in_pct']:.1f} %")
    lines.append(f"breach nahoru:  {a['breach_up_pct']:.1f} %")
    lines.append(f"breach dolu:    {a['breach_dn_pct']:.1f} %")
    lines.append(f"avg band width: +/- {a['avg_band_bps']:.0f} bps")
    lines.append("")
    lines.append("Po letech:")
    lines.append("  rok    n    stayed  pct")
    for y, n, s, p in a["per_year"]:
        lines.append(f"  {y}  {n:4d}  {s:4d}   {p:5.1f} %")
    lines.append("")
    lines.append("Podle VIX kvintilu (prev-day close):")
    lines.append("  kv  rozsah VIX     n    stayed  pct")
    for i, lo, hi, n, s, p in a["per_vix_q"]:
        lo_s = f"{lo:.1f}" if lo != float("-inf") else "-inf"
        hi_s = f"{hi:.1f}" if hi != float("inf") else "+inf"
        lines.append(f"  Q{i+1}  {lo_s:>5}-{hi_s:<5}  {n:4d}  {s:4d}   {p:5.1f} %")
    return "\n".join(lines)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("json_path")
    args = ap.parse_args()
    rows = load(args.json_path)
    if not rows:
        print("Nula validnich radku.", file=sys.stderr); sys.exit(1)
    print(fmt(analyze(rows)))
