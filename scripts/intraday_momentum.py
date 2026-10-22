"""Intraday momentum (Gao, Han, Li & Zhou 2018, JFE): the first half-hour
return (prior close to 10:00, overnight included) predicts the last half-hour
return. Rule fixed before looking: at 15:30 go long if the prior-close-to-10:00
return is positive, short if negative; exit 15:55. Variants shown: the 10:00-15:30
return as predictor too (Gao's second predictor), and both agreeing.
NQ points per MNQ net of 0.75 pt. Data: NOISETOD P tags (half-hour prices).

Usage: intraday_momentum.py SCRATCH_DIR
"""
from __future__ import annotations

import math
import statistics as st
import sys

sys.path.insert(0, "scripts")
from score_noise_tod import parse  # noqa: E402


def stat(v):
    if len(v) < 3:
        return "n<3"
    sd = st.pstdev(v)
    return f"{st.mean(v):+6.2f} pt t{st.mean(v) / sd * math.sqrt(len(v)):+4.1f} n{len(v):>4} WR {sum(x > 0 for x in v) / len(v) * 100:3.0f}%"


def main():
    _, P = parse(f"{sys.argv[1]}/NOISETOD_tags.txt")
    rules = {
        "first half-hour (incl. overnight)": lambda p: p["px"][1] - p["pc"],
        "10:00-15:30 return": lambda p: p["px"][12] - p["px"][1],
        "both agree": lambda p: (p["px"][1] - p["pc"]) if (p["px"][1] - p["pc"]) * (p["px"][12] - p["px"][1]) > 0 else 0,
        "first half-hour, RTH only": lambda p: p["px"][1] - p["px"][0],
    }
    print(f"{len(P)} days\n")
    for name, f in rules.items():
        res = {"a": [], "b": []}
        for p in P:
            s = f(p)
            if s == 0:
                continue
            side = 1 if s > 0 else -1
            x = side * (p["px"][13] - p["px"][12]) - 0.75
            res["a" if p["ymd"] < "2022" else "b"].append(x)
        print(f"{name:<34} 2018-21 {stat(res['a'])}  |  2022-25 {stat(res['b'])}")


if __name__ == "__main__":
    main()
