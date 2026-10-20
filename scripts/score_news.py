"""Score the news-candle exporter: fade or follow the big release candle.

For every slot / timeframe / size filter the full target x stop x time grid
is evaluated in both directions. Each grid cell is a trade rule; the score is
the mean result in units of the risk taken (R = stop distance), so cells with
very different stops compare fairly. A cell is chosen on 2018-2021 and its
2022-2025 result is reported untouched, because a grid this large always
contains something that looks good in-sample.

Usage: score_news.py TAGFILE [TAGFILE ...]
"""
from __future__ import annotations

import math
import statistics as st
import sys
from collections import defaultdict

FB = [0.25, 0.382, 0.5, 0.618, 0.75, 1.0, 1.25]
AK = [0.0, 0.1, 0.25, 0.5, 1.0]
AR = [0.25, 0.5]
HZ = [5, 15, 30, 60, 120, 180]
TICK = {"NQ": 0.25, "ES": 0.25, "YM": 1.0}
SPLIT = "20220101"
STOP_NAMES = [f"ext+{k:g}R" for k in AK] + [f"{a:g}R" for a in AR]


def parse(paths):
    ev, side = [], defaultdict(list)
    for p in paths:
        for line in open(p):
            f = line.strip().split(",")
            if f[0] == "N" and len(f) >= 34:
                O, H, L, C = map(float, f[8:12])
                inst = f[1]
                body, rng = abs(C - O), H - L
                wick = (H - C) if C > O else (C - L)
                ev.append({
                    "inst": inst, "kind": f[2], "s": int(f[3]), "tf": int(f[4]),
                    "ymd": f[5], "fomc": f[6] == "1", "dow": int(f[7]),
                    "ratio": float(f[12]), "body": body, "rng": rng,
                    "tgt": [x * body for x in FB],
                    "stp": [wick + TICK[inst] + k * rng for k in AK] + [a * rng for a in AR],
                    "tb": [int(x) for x in f[13:20]], "sb": [int(x) for x in f[20:27]],
                    "m": [float(x) for x in f[27:33]], "eod": float(f[33]),
                })
            elif f[0] in ("L", "F"):
                side[f[0]].append(f)
    return ev, side


def outcome(e, ti, sj, hi, follow=False):
    """Points and risk for one rule. ti/sj may be None; hi indexes HZ, or None = EOD."""
    H = HZ[hi] if hi is not None else 10 ** 6
    if not follow:
        t = e["tb"][ti] if ti is not None else -1
        s = e["sb"][sj] if sj is not None else -1
        win = e["tgt"][ti] if ti is not None else None
        loss = e["stp"][sj] if sj is not None else None
        mtm = e["m"][hi] if hi is not None else e["eod"]
    else:  # follow the candle: fade stops become targets and vice versa
        t = e["sb"][sj] if sj is not None else -1
        s = e["tb"][ti] if ti is not None else -1
        win = e["stp"][sj] if sj is not None else None
        loss = e["tgt"][ti] if ti is not None else None
        mtm = -(e["m"][hi] if hi is not None else e["eod"])
    t = t if 0 <= t <= H else -1
    s = s if 0 <= s <= H else -1
    if s >= 0 and (t < 0 or s <= t):
        pts = -loss
    elif t >= 0:
        pts = win
    else:
        pts = mtm
        if loss is not None:
            pts = max(pts, -loss)
    # A stop just past a candle that closed on its extreme can be one tick
    # away; floor the risk at a quarter of the candle so R stays meaningful.
    risk = max(loss, 0.25 * e["rng"]) if loss is not None else e["rng"]
    return pts, risk


def tstat(v):
    if len(v) < 3:
        return 0.0
    sd = st.pstdev(v)
    return st.mean(v) / sd * math.sqrt(len(v)) if sd > 0 else 0.0


def grid(evs, follow):
    # A prop account needs a hard stop: for a fade that is a stop level, for
    # a follow it is a retracement level toward the candle's open.
    tis = list(range(len(FB))) if follow else [None] + list(range(len(FB)))
    sjs = [None] + list(range(len(STOP_NAMES))) if follow else list(range(len(STOP_NAMES)))
    his = [1, 3, 5, None]          # 15m, 60m, 180m, 15:55
    for ti in tis:
        for sj in sjs:
            for hi in his:
                yield (ti, sj, hi), [outcome(e, ti, sj, hi, follow) for e in evs]


def rname(key, follow):
    ti, sj, hi = key
    tg = "-" if ti is None else f"{FB[ti]:g}body"
    sp = "-" if sj is None else STOP_NAMES[sj]
    if follow:   # targets beyond the extreme, stop on a retracement
        tg, sp = ("-" if sj is None else "past " + STOP_NAMES[sj]), ("-" if ti is None else f"{FB[ti]:g}body back")
    hz = "EOD" if hi is None else f"{HZ[hi]}m"
    return f"{'FOLLOW' if follow else 'FADE'} tgt {tg:<9} stop {sp:<9} time {hz}"


def summarise(rs):
    r = [p / k for p, k in rs if k > 0]
    p = [p for p, _ in rs]
    return {"n": len(rs), "R": st.mean(r) if r else 0.0, "tR": tstat(r),
            "pts": st.mean(p) if p else 0.0,
            "wr": sum(1 for x in p if x > 0) / len(p) * 100 if p else 0.0}


def family_report(name, evs):
    is_ = [e for e in evs if e["ymd"] < SPLIT]
    oos = [e for e in evs if e["ymd"] >= SPLIT]
    if len(is_) < 25 or len(oos) < 25:
        print(f"{name:<34} n={len(evs):4}  too few")
        return None
    best = None
    for follow in (False, True):
        for key, rs in grid(is_, follow):
            s = summarise(rs)
            if best is None or s["tR"] > best[0]["tR"]:
                best = (s, key, follow)
    s_is, key, follow = best
    s_oos = summarise([outcome(e, *key, follow) for e in oos])
    # the user's rule as stated: fade to the candle's open, stop past its extreme
    u_is = summarise([outcome(e, 5, 0, None) for e in is_])
    u_oos = summarise([outcome(e, 5, 0, None) for e in oos])
    print(f"{name:<34} n={len(is_):4}/{len(oos):4}  best IS: {rname(key, follow)}")
    print(f"{'':<34}   IS  {s_is['R']:+.3f}R t{s_is['tR']:+.1f} wr{s_is['wr']:3.0f}%"
          f"   OOS {s_oos['R']:+.3f}R t{s_oos['tR']:+.1f} wr{s_oos['wr']:3.0f}% {s_oos['pts']:+.1f}pt")
    print(f"{'':<34}   your rule (fade->open, stop past extreme, EOD): "
          f"IS {u_is['R']:+.3f}R t{u_is['tR']:+.1f}  OOS {u_oos['R']:+.3f}R t{u_oos['tR']:+.1f}")
    return {"name": name, "key": key, "follow": follow, "is": s_is, "oos": s_oos}


def user_table(fams):
    """The idea as stated: fade the release candle toward its open or halfway."""
    print("\n== your idea: fade the candle; IS 2018-21 | OOS 2022-25, mean points (R)")
    rules = [(5, 0, None, "to open, stop past extreme, EOD"),
             (5, 2, None, "to open, stop extreme+0.25R, EOD"),
             (2, 0, None, "to 50%, stop past extreme, EOD"),
             (2, 2, 3, "to 50%, stop extreme+0.25R, 60m"),
             (5, 2, 3, "to open, stop extreme+0.25R, 60m")]
    for key in sorted(fams):
        inst, lab, thr = key
        if not (lab.startswith(("08:30 5m", "FOMC", "ANY")) and thr in (0.0, 2.5, 3.0)):
            continue
        evs = fams[key]
        print(f"  {inst} {lab} ratio>={thr:g}")
        for ti, sj, hi, name in rules:
            row = []
            for part in ([e for e in evs if e["ymd"] < SPLIT], [e for e in evs if e["ymd"] >= SPLIT]):
                rs = [outcome(e, ti, sj, hi) for e in part]
                s_ = summarise(rs)
                row.append(f"n{s_['n']:4} {s_['pts']:+7.1f}pt ({s_['R']:+.2f}R t{s_['tR']:+.1f})")
            print(f"     {name:<36} {row[0]} | {row[1]}")


def side_tests(side):
    L = side.get("L", [])
    if L:
        print("\n== last half-hour momentum (enter 15:30 in the sign of the first half-hour, exit 15:55)")
        for thr in (0.0, 0.0025, 0.005, 0.01):
            for lo, hi_, lab in (("0", SPLIT, "IS"), (SPLIT, "9", "OOS")):
                v = []
                for f in L:
                    if not (lo <= f[2] < hi_):
                        continue
                    pc, o930, p10, p1530, p1555 = map(float, f[4:9])
                    r1 = p10 / pc - 1.0
                    if abs(r1) < thr:
                        continue
                    v.append((1 if r1 > 0 else -1) * (p1555 - p1530))
                print(f"   |r1|>={thr*100:.2f}%  {lab:<3} n={len(v):4}  {st.mean(v) if v else 0:+.2f} pt  t{tstat(v):+.1f}")
    F = side.get("F", [])
    if F:
        print("\n== pre-FOMC drift (long into the 14:00 statement)")
        for lab, ix in (("09:30->13:55", 3), ("10:00->13:55", 4)):
            for lo, hi_, per in (("0", SPLIT, "IS"), (SPLIT, "9", "OOS")):
                v = [float(f[5]) - float(f[ix]) for f in F if lo <= f[2] < hi_]
                print(f"   {lab} {per:<3} n={len(v):3}  {st.mean(v) if v else 0:+.2f} pt  t{tstat(v):+.1f}  "
                      f"wr {sum(1 for x in v if x > 0)/max(1,len(v))*100:.0f}%")


def main():
    ev, side = parse(sys.argv[1:])
    print(f"{len(ev)} candle events")
    fams = defaultdict(list)
    for e in ev:
        if e["kind"] == "A":
            fams[(e["inst"], "ANY climax 5m", 3.0)].append(e)
            continue
        lab = {510: "08:30", 600: "10:00", 840: "14:00", 870: "14:30"}[e["s"]]
        for thr in (1.8, 2.5, 3.5, 5.0):
            if e["ratio"] >= thr:
                fams[(e["inst"], f"{lab} {e['tf']}m", thr)].append(e)
        if e["fomc"] and e["s"] >= 840:
            fams[(e["inst"], f"FOMC {lab} {e['tf']}m", 0.0)].append(e)
    out = []
    for (inst, lab, thr), evs in sorted(fams.items()):
        r = family_report(f"{inst} {lab} ratio>={thr:g}", evs)
        if r:
            out.append(r)
    good = [r["name"] for r in out if r["oos"]["tR"] >= 2.0]
    print(f"\n{len(out)} families; OOS t >= 2: {', '.join(good) or 'none'}")
    user_table(fams)
    side_tests(side)


if __name__ == "__main__":
    main()
