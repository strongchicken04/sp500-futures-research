"""More two-account pairs with the hedge guard (2026-10-23): 09:31 trend +
VWAP-side sprint at 11:00 (0.30/0.50) and RS + VWAP11; vs RS + 09:31 (now).
The later entry skips when the other account holds an opposite open position.
Usage: pair_guard2.py DATA_DIR
"""
from __future__ import annotations

import sys

sys.path.insert(0, "scripts")
from prop_sim import Trade  # noqa: E402
from score_multi_feature import parse as parse_mf, first_signals  # noqa: E402
from score_cond_bracket import parse, LEVELS  # noqa: E402
from hedge_check import a_usd, b_usd, exit_min, CLV  # noqa: E402
from b_sprint_lab import trend_map, sgn  # noqa: E402
from pair_sprint import ERAS  # noqa: E402
from pair_guard import first_funded  # noqa: E402


def c_usd(r, s, tp, sp):
    ti, si = LEVELS.index(tp), LEVELS.index(sp)
    fav, adv = (r["up"], r["dn"]) if s == 1 else (r["dn"], r["up"])
    t, sl = fav[ti], adv[si]
    T, S = r["e"] * tp / 1e4, r["e"] * sp / 1e4
    if sl >= 0 and (t < 0 or sl <= t):
        p = -S - 0.25
    elif t >= 0:
        p = T
    else:
        p = max(-S - 0.25, s * r["eod"] - 0.25)
    n = max(1, min(40, int(1900 / (S * 2.0))))
    return (p - 0.25) * 2.0 * n - n


def xmin(r, s, e_min, tp, sp):
    fav, adv = (r["up"], r["dn"]) if s == 1 else (r["dn"], r["up"])
    return exit_min(e_min, fav, adv, LEVELS.index(tp), LEVELS.index(sp))


def main():
    data = sys.argv[1]
    for lab, lo, hi, suf in ERAS:
        rs = {d: v for d, v in first_signals(parse_mf(f"{data}/MFEAT{suf}_tags.txt"), lambda r: 1 if (r["rs"] > 0.0015 and r["vwapd"] > 0) else
                                             (-1 if (r["rs"] < -0.0015 and r["vwapd"] < 0) else 0)).items() if lo <= d < hi}
        R = {}
        for r in parse([f"{data}/CBA{suf}_tags.txt"]):
            R.setdefault(r["type"], []).append(r)
        tm = trend_map(R["T931"])
        t9 = {r["date"]: (r, tm[r["date"]]) for r in R["T931"] if lo <= r["date"] < hi and tm.get(r["date"])}
        v11 = {r["date"]: (r, sgn(r["e"] - r["vwap"])) for r in R["T1100"] if lo <= r["date"] < hi and sgn(r["e"] - r["vwap"])}
        cal = sorted(set(rs) | set(t9) | set(v11))
        t9x = {d: xmin(r, s, 571, 25, 40) for d, (r, s) in t9.items()}
        T9 = [Trade(d, b_usd(r, s), "S") for d, (r, s) in t9.items()]
        # RS + 09:31 (now): RS skips against an open 09:31 trade
        A = [Trade(d, a_usd(r, s), "S") for d, (r, s) in rs.items() if not (d in t9 and t9[d][1] != s and r["hm"] < t9x[d])]
        now = first_funded(A, T9, cal)
        # 09:31 + VWAP11: VWAP11 skips against an open 09:31 trade
        V = [Trade(d, c_usd(r, s, 30, 50), "S") for d, (r, s) in v11.items() if not (d in t9 and t9[d][1] != s and 660 < t9x[d])]
        p2 = first_funded(V, T9, cal)
        # RS + VWAP11: VWAP11 skips against an open RS trade entered before 11:00; RS entered after 11:00 skips against VWAP11
        rsx = {d: xmin(r, s, r["hm"], 20, 30) for d, (r, s) in rs.items()}
        v11x = {d: xmin(r, s, 660, 30, 50) for d, (r, s) in v11.items()}
        V2, A2 = [], []
        for d, (r, s) in v11.items():
            if d in rs and rs[d][1] != s and rs[d][0]["hm"] <= 660 < rsx[d]:
                continue
            V2.append(Trade(d, c_usd(r, s, 30, 50), "S"))
        for d, (r, s) in rs.items():
            if d in v11 and v11[d][1] != s and 660 < r["hm"] < v11x[d]:
                continue
            A2.append(Trade(d, a_usd(r, s), "S"))
        p3 = first_funded(A2, V2, cal)
        print(f"{lab}: RS + 09:31 (now) {now[0]:5.1f} d ${now[1]:4.0f} | 09:31 + VWAP11 {p2[0]:5.1f} d ${p2[1]:4.0f} | RS + VWAP11 {p3[0]:5.1f} d ${p3[1]:4.0f}")


if __name__ == "__main__":
    main()
