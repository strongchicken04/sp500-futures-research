"""POST-HOC follow-up of eval931_features.py (2026-11-04): the scan's survivors
are two known ideas - overnight reversal (fade the gap) and closing strength
of the prior day (IBS > .5, close above VWAP, last-hour BVC delta). Votes:
V = -sign(gap) + sign(prior close vs VWAP) + sign(IBS - .5) + sign(last-hour
delta); trade sign(V) when |V| >= 2 (or >= 3). Chosen AFTER seeing the scan ->
optimistic, information only. Usage: eval931_posthoc.py DATA_DIR
"""
import sys
sys.path.insert(0, "scripts")
import eval931_features as X  # noqa: E402
import eval_25k as E  # noqa: E402


def vote(c):
    if c.get("ibs") is None or c.get("pvwap") is None or c.get("lhdelta") is None:
        return 0
    return -X.sgn(c["gap"], 0.0005) + X.sgn(c["pvwap"]) + X.sgn(c["ibs"] - 0.5) + X.sgn(c["lhdelta"], 0.05)


def main():
    data = sys.argv[1]
    rows = X.load(data)
    ctx = X.build(rows, X.panels(data), X.xmkt(data))
    hdr = " | ".join(f"{e[0]:^22s}" for e in X.ERAS)
    print(f"{'rule (POST-HOC)':<26s} {hdr} |   z")
    tests = [("SMA50 (Lucid 7)", lambda c: c["sma"] or 0),
             ("vote |V|>=2", lambda c: X.sgn(vote(c)) if abs(vote(c)) >= 2 else 0),
             ("vote |V|>=3", lambda c: X.sgn(vote(c)) if abs(vote(c)) >= 3 else 0),
             ("vote sign (any)", lambda c: X.sgn(vote(c))),
             ("vote, else SMA50", lambda c: X.sgn(vote(c)) or (c["sma"] or 0))]
    for name, fn in tests:
        sc, z = X.scan(rows, ctx, fn)
        print(f"{name:<26s} " + " | ".join(f"{X.cell(s):^22s}" for s in sc) + f" | {z:+5.1f}")
    print("\n50K evaluation (INTRA, NQ 28,530): days | fees")
    by = {r["date"]: (r, c) for r, c in zip(rows, ctx)}
    for _, lo, hi in X.ERAS[:4]:
        cal = [r["date"] for r in rows if lo <= r["date"] < hi]
        cells = []
        for name, fn in tests:
            sig = {d: E.scaled(by[d][0], fn(by[d][1]), 20, 40) for d in cal if fn(by[d][1])}
            dd, ev, _ = E.run(sig, cal, E.ACC["50K"])
            cells.append(f"{name} {dd:4.1f}d ${ev * 90:3.0f}")
        print(f"   {lo}-{int(hi) - 1}: " + " | ".join(cells))


if __name__ == "__main__":
    main()
