#!/usr/bin/env python3
"""Analyze first-touch bias: ONH vs ONL depending on open side of ONM.

Vstup: JSON pole zaznamu z QC exporteru onh_onl_first_touch:
  [{"date": "...", "rth_open": ..., "onh": ..., "onl": ..., "onm": ...,
    "first": "H|L|B|N", "open_side": "A|B|M"}, ...]

Vypocty:
  Otevreno NAD midpointem (side="A"):
    % dni ONH hit before ONL (first="H")
    % dni ONL hit first (first="L")
    % neither (first="N")
  Otevreno POD midpointem (side="B"):
    zrcadlove
Ambivalentni same-minute (first="B") reportujeme zvlast (nezapocitava se
do H ani L pro cistotu).
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path


def load(path):
    return json.loads(Path(path).read_text())


def analyze(rows):
    out = {}
    for label, side_flag in (("open ABOVE ONM", "A"), ("open BELOW ONM", "B")):
        subset = [r for r in rows if r["open_side"] == side_flag]
        n = len(subset)
        if n == 0:
            out[label] = {"n": 0}
            continue
        cnt = Counter(r["first"] for r in subset)
        out[label] = dict(
            n=n,
            H=cnt.get("H", 0), H_pct=100.0 * cnt.get("H", 0) / n,
            L=cnt.get("L", 0), L_pct=100.0 * cnt.get("L", 0) / n,
            B=cnt.get("B", 0), B_pct=100.0 * cnt.get("B", 0) / n,
            N=cnt.get("N", 0), N_pct=100.0 * cnt.get("N", 0) / n,
        )
    # also total
    n = len(rows)
    cnt = Counter(r["first"] for r in rows)
    out["TOTAL"] = dict(
        n=n,
        H=cnt.get("H", 0), H_pct=100.0 * cnt.get("H", 0) / max(n, 1),
        L=cnt.get("L", 0), L_pct=100.0 * cnt.get("L", 0) / max(n, 1),
        B=cnt.get("B", 0), B_pct=100.0 * cnt.get("B", 0) / max(n, 1),
        N=cnt.get("N", 0), N_pct=100.0 * cnt.get("N", 0) / max(n, 1),
    )
    return out


def fmt(a):
    lines = []
    for k in ("open ABOVE ONM", "open BELOW ONM", "TOTAL"):
        s = a[k]
        if s.get("n", 0) == 0:
            lines.append(f"[{k}] 0 days")
            continue
        lines.append(f"[{k}]  n = {s['n']}")
        lines.append(f"  first-touch ONH  : {s['H']:4d}  ({s['H_pct']:5.1f} %)")
        lines.append(f"  first-touch ONL  : {s['L']:4d}  ({s['L_pct']:5.1f} %)")
        lines.append(f"  both same minute : {s['B']:4d}  ({s['B_pct']:5.1f} %)")
        lines.append(f"  neither          : {s['N']:4d}  ({s['N_pct']:5.1f} %)")
        # Ktera strana dominuje (ignoruje B a N)
        eff = s['H'] + s['L']
        if eff > 0:
            hpct = 100.0 * s['H'] / eff
            lpct = 100.0 * s['L'] / eff
            lines.append(f"  --> conditional (only H or L hit, n={eff}): "
                         f"H {hpct:.1f} %   L {lpct:.1f} %")
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("json_path")
    args = ap.parse_args()
    rows = load(args.json_path)
    if not rows:
        print("Nula radku.", file=sys.stderr); sys.exit(1)
    print(fmt(analyze(rows)))
