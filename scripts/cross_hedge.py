"""Cross-account hedging between the funded book and the evaluation sprints
(night shift 2026-10-23/24). Lucid bans opposite positions across one's own
accounts. While new evaluations run (after every bust), the funded seats trade
the book (VG + Z + RS, + OD optional) and the evaluation accounts trade the
RS sprint (A, 0.20/0.30) and the 09:31 trend sprint (B, 0.25/0.40).
Measured 2018-25: share of days on which a sprint position and an OPPOSITE
book position are open at the same time; split into "book already holds the
opposite side when the sprint enters" (sprint would have to skip) and "the book
enters against an open sprint" (book trade would have to skip), plus the P&L of
the book trades that would be skipped.
Usage: cross_hedge.py DATA_DIR
"""
from __future__ import annotations

import statistics as st
import sys

sys.path.insert(0, "scripts")
import mtm_check as C  # noqa: E402
from rescore_all import rvol  # noqa: E402
from score_multi_feature import parse as parse_mf, first_signals, LEVELS as ML  # noqa: E402
from score_cond_bracket import parse, LEVELS as CL  # noqa: E402
from b_sprint_lab import trend_map  # noqa: E402

EODM = 955


def sprint_times(r, s, lv, tp, sp):
    fav, adv = (r["up"], r["dn"]) if s == 1 else (r["dn"], r["up"])
    hits = [k for k in (fav[lv.index(tp)], adv[lv.index(sp)]) if k >= 0]
    return r["hm"], min(EODM, r["hm"] + min(hits)) if hits else EODM


def main():
    data = sys.argv[1]
    reg = rvol()
    book, _ = C.trades(data, "", lambda d: reg.get(d, 9.0) < 0.30, None)
    B = {}
    for t in book:
        B.setdefault(t[0], []).append(t)
    rs = first_signals(parse_mf(f"{data}/MFEAT_tags.txt"), lambda r: 1 if (r["rs"] > 0.0015 and r["vwapd"] > 0) else
                       (-1 if (r["rs"] < -0.0015 and r["vwapd"] < 0) else 0))
    S = {"RS sprint (A)": {d: (s,) + sprint_times(r, s, ML, 20, 30) for d, (r, s) in rs.items()}}
    R = {}
    for r in parse([f"{data}/CBA_tags.txt"]):
        R.setdefault(r["type"], []).append(r)
    tm = trend_map(R["T931"])
    S["09:31 sprint (B)"] = {r["date"]: (tm[r["date"]],) + sprint_times(r, tm[r["date"]], CL, 25, 40) for r in R["T931"] if tm.get(r["date"])}
    S["VWAP10 sprint"] = {r["date"]: ((1 if r["e"] > r["vwap"] else -1),) + sprint_times(r, (1 if r["e"] > r["vwap"] else -1), CL, 25, 40)
                          for r in R["T1000"] if r["e"] != r["vwap"]}
    for legs in (("VG", "Z", "RS"), ("VG", "Z", "RS", "OD")):
        print(f"--- book {'+'.join(legs)}")
        for name, sp in S.items():
            for lo, hi in (("2018", "2022"), ("2022", "2026")):
                days = [d for d in sp if lo <= d < hi]
                pre = post = anyc = 0
                skipped = []
                for d in days:
                    s, e, x = sp[d]
                    hit_pre = hit_post = False
                    for t in B.get(d, []):
                        if t[4] not in legs or t[5] == s:
                            continue
                        if t[1] <= e < t[2]:
                            hit_pre = True
                        elif e < t[1] < x:
                            hit_post = True
                            skipped.append(t[3])
                    pre += hit_pre
                    post += hit_post
                    anyc += hit_pre or hit_post
                n = len(days)
                print(f"   {name:<16} {lo}-{int(hi) - 1}: sprint days {n}, clash {anyc / n * 100:4.1f}% "
                      f"(book already opposite at sprint entry {pre / n * 100:4.1f}%, book enters against the sprint "
                      f"{post / n * 100:4.1f}%; those book trades {len(skipped)}, mean ${st.mean(skipped) if skipped else 0:+.1f} per MNQ)")


if __name__ == "__main__":
    main()
