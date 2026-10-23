"""All funded comparisons on the corrected account model (funded_model.py:
all days, five-profitable-day payout rule, withdrawals keep the excess).
Night shift 2026-10-23/24; variants fixed before results (same as the earlier
scripts book_recheck / payout_size / funded_sprint, which used the old model):
  books   base = no ORB (VG + Z + RS) flat 3 | + ORB | flat 2 | flat 4 | flat 5 | flat 6 (plateau check, added after flat 4 won) | no RS |
          Z without the vol gate
  sizing  F2 (2 MNQ when < $1,000 from +$4,000) | P2 (2 MNQ once +$4,000 with
          < 5 profitable days) | F2+P2
  sprint  RS / VWAP10 sprint until the first payout (S3 big wins, S5 five
          wins), then the base book
Paired block bootstrap 24 months, 2018-21 / 2022-25; first-payout rate and
mean days to it from every start day.
Usage: funded_v2.py DATA_DIR
"""
from __future__ import annotations

import statistics as st
import sys

sys.path.insert(0, "scripts")
import gate_check as G  # noqa: E402
import funded_model as M  # noqa: E402
from funded_sprint import sprint_usd  # noqa: E402
from mc_runs import sized  # noqa: E402
from score_multi_feature import parse as parse_mf, first_signals, LEVELS as ML  # noqa: E402
from score_cond_bracket import parse, LEVELS as CL  # noqa: E402
from b_sprint_lab import sgn  # noqa: E402
from two_win_sprint import trade_pts  # noqa: E402


def lists(tr, cal):
    by = {}
    for t in tr:
        by.setdefault(t[0], []).append(t)
    return [[t[3] for t in sorted(by.get(d, []), key=lambda t: t[2])] for d in cal]


def sized_fn(rule):
    def f(day, s):
        n = 3
        near = s["pnl"] < 4000.0 and 4000.0 - s["pnl"] < 1000.0
        wait = s["pnl"] >= 4000.0 and s["pdays"] < 5
        if (rule in ("F2", "F2+P2") and near) or (rule in ("P2", "F2+P2") and wait):
            n = 2
        return [u * n for u in day["base"]]
    return f


def sprint_fn(kind, size):
    def f(day, s):
        if s["pays"] > 0:
            return [u * 3 for u in day["base"]]
        sig = day[kind]
        return [sprint_usd(sig, s["pnl"], s["line"], s["peak"], s["pdays"], size)] if sig else []
    return f


def main():
    data = sys.argv[1]
    g, zf = G.build(data, set()), G.build(data, {"Z"})
    one = {"base": sized(g, {"VG": 1, "Z": 1, "RS": 1}), "orb": sized(g, {"ORB": 1, "VG": 1, "Z": 1, "RS": 1}),
           "nors": sized(g, {"VG": 1, "Z": 1}), "zfree": sized(zf, {"VG": 1, "Z": 1, "RS": 1})}
    rs = first_signals(parse_mf(f"{data}/MFEAT_tags.txt"), lambda r: 1 if (r["rs"] > 0.0015 and r["vwapd"] > 0) else
                       (-1 if (r["rs"] < -0.0015 and r["vwapd"] < 0) else 0))
    rs = {d: trade_pts(r, s, ML, 20, 30) for d, (r, s) in rs.items()}
    cba = parse([f"{data}/CBA_tags.txt"])
    vw = {r["date"]: trade_pts(r, sgn(r["e"] - r["vwap"]), CL, 25, 40) for r in cba if r["type"] == "T1000" and sgn(r["e"] - r["vwap"])}
    full = sorted({r["date"] for r in cba})
    V = {"base (no ORB, flat 3)": lambda d, s: [u * 3 for u in d["base"]],
         "+ ORB": lambda d, s: [u * 3 for u in d["orb"]],
         "flat 2": lambda d, s: [u * 2 for u in d["base"]],
         "flat 4": lambda d, s: [u * 4 for u in d["base"]],
         "flat 5": lambda d, s: [u * 5 for u in d["base"]],
         "flat 6": lambda d, s: [u * 6 for u in d["base"]],
         "no RS": lambda d, s: [u * 3 for u in d["nors"]],
         "Z without vol gate": lambda d, s: [u * 3 for u in d["zfree"]],
         "F2": sized_fn("F2"), "P2": sized_fn("P2"), "F2+P2": sized_fn("F2+P2"),
         "RS sprint S3 -> book": sprint_fn("rs", "S3"), "RS sprint S5 -> book": sprint_fn("rs", "S5"),
         "VWAP10 sprint S3 -> book": sprint_fn("vw", "S3"), "VWAP10 sprint S5 -> book": sprint_fn("vw", "S5")}
    for lo, hi, lab in (("2018", "2022", "2018-21"), ("2022", "2026", "2022-25")):
        cal = [d for d in full if lo <= d < hi]
        L = {k: lists(v, cal) for k, v in one.items()}
        days = [{"base": L["base"][i], "orb": L["orb"][i], "nors": L["nors"][i], "zfree": L["zfree"][i],
                 "rs": rs.get(d), "vw": vw.get(d)} for i, d in enumerate(cal)]
        paths = M.bootstrap(len(days), 4000, seed=2610)
        print(f"--- {lab}: 24-month cash per funded seat (paired bootstrap) | first payout from every start day")
        base = None
        for name, fn in V.items():
            cash = [M.run_path([days[i] for i in p], fn) for p in paths]
            fp = [x for x in (M.first_payout(days[s:], fn) for s in range(len(days) - 250)) if x]
            ok = [n for r, n in fp if r]
            base = base or cash
            dd = [x - y for x, y in zip(cash, base)]
            sv = sorted(cash)
            print(f"   {name:<26} mean ${st.mean(cash):7,.0f} (${st.mean(cash) / 24:5,.0f}/m) p10 ${sv[len(sv) // 10]:7,.0f} "
                  f"vs base {st.mean(dd):+7,.0f} (+/- {1.96 * st.pstdev(dd) / len(dd) ** 0.5:,.0f}) "
                  f"better/worse {sum(x > 0 for x in dd) / len(dd) * 100:3.0f}/{sum(x < 0 for x in dd) / len(dd) * 100:3.0f}% | "
                  f"first payout {len(ok) / len(fp) * 100:4.1f}% in {st.mean(ok):4.1f} d")


if __name__ == "__main__":
    main()
