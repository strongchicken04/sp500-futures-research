"""Funded decisions in 2010-2017 at TODAY's price level (night shift
2026-10-23/24, fixed before results). Dollars in 2010-17 are 4-6x smaller
(NQ 2,000-6,000), so account sims there say nothing. Here every 2010-17
trade keeps its GROSS return in % of price, is re-priced at the mean 2022-25
NQ entry price, and today's costs are subtracted (0.75 pt, 1.0 pt on stops,
per MNQ $2 / pt): "what if today's market behaved like 2010-17".
Legs as old_check.legs (live specs; vol gate prior-day rv20 < 0.30; ORB and VG
not on Wednesdays; RS +/-1.25% else 15:55). Same variants as funded_v2:
base (no ORB, flat 3), flat 4, + ORB, Z without the vol gate; corrected
account model (funded_model.py). Paired bootstrap, 2010-13 / 2014-17.
Usage: funded_scaled_old.py DATA_DIR
"""
from __future__ import annotations

import datetime as dt
import statistics as st
import sys

sys.path.insert(0, "scripts")
import funded_model as M  # noqa: E402
from score_multi_feature import parse as parse_mf, first_signals, LEVELS  # noqa: E402
from score_cond_bracket import parse  # noqa: E402

EOD = 955


def ls_rows(path, var):
    out = []
    for raw in open(path):
        f = raw.strip().split(",")
        if f[0] != "L" or len(f) < 10 or f[1] != var:
            continue
        d, e, x = int(f[3]), float(f[5]), float(f[7])
        out.append({"date": f"{f[2][:4]}-{f[2][4:6]}-{f[2][6:]}", "ret": d * (x - e) / e, "stop": f[8] in ("SL", "STOP"),
                    "rv": int(f[9]) / 1000.0, "ehm": int(f[4]), "xhm": int(f[6]), "e": e})
    return out


def legs(data, suffix):
    files = {"ORB": ("LSORB" + suffix, "O5"), "VG": ("LSVWAP" + suffix, "B5"), "Z": ("LSNOISE" + suffix, "NS")}
    raw = {k: ls_rows(f"{data}/{f}_tags.txt", v) for k, (f, v) in files.items()}
    reg = {t["date"]: t["rv"] for k in raw for t in raw[k] if t["rv"] > 0}
    out = []
    for leg, rows in raw.items():
        for t in rows:
            out.append((t["date"], t["ehm"], t["xhm"], t["ret"], 1.0 if t["stop"] else 0.75, leg, t["e"]))
    sig = first_signals(parse_mf(f"{data}/MFEAT{suffix}_tags.txt"), lambda r: 1 if (r["rs"] > 0.0015 and r["vwapd"] > 0) else
                        (-1 if (r["rs"] < -0.0015 and r["vwapd"] < 0) else 0))
    ti = si = LEVELS.index(125)
    for d, (r, s) in sig.items():
        fav, adv = (r["up"], r["dn"]) if s == 1 else (r["dn"], r["up"])
        hits = [k for k in (fav[ti], adv[si]) if k >= 0]
        x = min(EOD, r["hm"] + min(hits)) if hits else EOD
        t_, sl = fav[ti], adv[si]
        if sl >= 0 and (t_ < 0 or sl <= t_):
            ret, c = -0.0125, 1.0
        elif t_ >= 0:
            ret, c = 0.0125, 0.75
        else:
            ret, c = max(-0.0125, s * r["eod"] / r["e"]), 0.75
        out.append((d, r["hm"], x, ret, c, "RS", r["e"]))
    out = [t for t in out if not (dt.date.fromisoformat(t[0]).weekday() == 2 and t[5] in ("ORB", "VG"))]
    gated = lambda d: 0 < reg.get(d, 9.0) < 0.30
    return out, gated


def main():
    data = sys.argv[1]
    pref = st.mean(t["e"] for t in ls_rows(f"{data}/LSNOISE_tags.txt", "NS") if t["date"] >= "2022")
    print(f"reference price (mean 2022-25 noise entry) {pref:,.0f}")
    old, gated = legs(data, "_OLD")
    full = sorted({r["date"] for r in parse([f"{data}/CBA_OLD_tags.txt"])})

    def lists(keep, zfree=False):
        by = {}
        for d, eh, xh, ret, c, leg, e in old:
            if leg in keep and (gated(d) or (zfree and leg == "Z")):
                by.setdefault(d, []).append((xh, (ret * pref - c) * 2.0))
        return {d: [u for _, u in sorted(v)] for d, v in by.items()}

    B = {"base": lists({"VG", "Z", "RS"}), "orb": lists({"ORB", "VG", "Z", "RS"}), "zfree": lists({"VG", "Z", "RS"}, True)}
    for k in ("ORB", "VG", "Z", "RS"):
        v = [(ret * pref - c) * 2.0 for d, eh, xh, ret, c, leg, e in old if leg == k and gated(d)]
        print(f"   {k:<3} per MNQ trade at today's price, 2010-17 gated: ${st.mean(v):+6.2f} (n {len(v)})")
    V = {"base (no ORB, flat 3)": lambda d, s: [u * 3 for u in d["base"]], "flat 4": lambda d, s: [u * 4 for u in d["base"]],
         "flat 5": lambda d, s: [u * 5 for u in d["base"]],
         "flat 6": lambda d, s: [u * 6 for u in d["base"]],
         "flat 2": lambda d, s: [u * 2 for u in d["base"]],
         "+ ORB": lambda d, s: [u * 3 for u in d["orb"]], "Z without vol gate": lambda d, s: [u * 3 for u in d["zfree"]]}
    for lo, hi, lab in (("2010", "2014", "2010-13"), ("2014", "2018", "2014-17")):
        cal = [d for d in full if lo <= d < hi]
        days = [{k: B[k].get(d, []) for k in B} for d in cal]
        paths = M.bootstrap(len(days), 4000, seed=2610)
        print(f"--- {lab} at today's price: 24-month cash per seat | first payout")
        base = None
        for name, fn in V.items():
            cash = [M.run_path([days[i] for i in p], fn) for p in paths]
            fp = [x for x in (M.first_payout(days[s:], fn) for s in range(len(days) - 250)) if x]
            base = base or cash
            dd = [x - y for x, y in zip(cash, base)]
            print(f"   {name:<22} mean ${st.mean(cash):7,.0f} vs base {st.mean(dd):+7,.0f} (+/- {1.96 * st.pstdev(dd) / len(dd) ** 0.5:,.0f}) "
                  f"better/worse {sum(x > 0 for x in dd) / len(dd) * 100:3.0f}/{sum(x < 0 for x in dd) / len(dd) * 100:3.0f}% | "
                  f"first payout {sum(r for r, _ in fp) / len(fp) * 100:4.1f}%")


if __name__ == "__main__":
    main()
