"""Screen fresh entry conditions under a fixed, prop-viable trade structure.

The lab archive makes the binding constraint obvious: all twenty of its
strategies average between -30 and -175 points on a losing trade, against -13
for the ORB rule that actually works, and every one of them scores under 35%
with a bust rate above 64%. On a trailing-drawdown account the shape of the
loss distribution decides the outcome, so a wide stop is disqualifying no
matter how good the entry is.

So the trade structure is held fixed at something survivable -- enter at the
open, hard stop a few points away, flat at the close -- and only the entry
condition varies. Daily OHLC resolves this honestly: a stop that sits inside
the day's range was hit, and holding to the close is an end-of-day decision.
What it cannot resolve is intrabar sequencing, so a day that touches both the
stop and a would-be target is scored as a loss.

Conditions are screened on average points and loss shape first, and only the
survivors are worth a barrier simulation.
"""
from __future__ import annotations

import statistics as st
import sys

sys.path.insert(0, "scripts")
from prop_sim import Trade, simulate, merge, TIERS  # noqa: E402
from daily_strategies import load_panel  # noqa: E402

STOP_PTS = 15.0


def build_context(bars: list[dict]) -> None:
    """Annotate each bar with the features the conditions are written against."""
    for i, b in enumerate(bars):
        b["i"] = i
        b["range"] = b["h"] - b["l"]
        b["body"] = b["c"] - b["o"]
        # Where the close sat inside the day's range, 0 at the low, 1 at the high.
        b["clv"] = (b["c"] - b["l"]) / b["range"] if b["range"] > 0 else 0.5
        b["ret"] = (b["c"] - bars[i - 1]["c"]) / bars[i - 1]["c"] if i else 0.0
        b["gap"] = (b["o"] - bars[i - 1]["c"]) / bars[i - 1]["c"] if i else 0.0
    for i, b in enumerate(bars):
        b["sma20"] = (sum(x["c"] for x in bars[i - 20:i]) / 20) if i >= 20 else None
        b["sma50"] = (sum(x["c"] for x in bars[i - 50:i]) / 50) if i >= 50 else None
        b["atr20"] = (sum(x["range"] for x in bars[i - 20:i]) / 20) if i >= 20 else None
        b["up_streak"] = 0
        j = i - 1
        while j >= 0 and bars[j]["ret"] > 0:
            b["up_streak"] += 1
            j -= 1
        b["dn_streak"] = 0
        j = i - 1
        while j >= 0 and bars[j]["ret"] < 0:
            b["dn_streak"] += 1
            j -= 1


def run(bars: list[dict], cond, direction: int, stop: float = STOP_PTS,
        name: str = "") -> list[Trade]:
    """Enter at the open when cond holds, hard stop, flat at the close."""
    out = []
    for i in range(51, len(bars)):
        b = bars[i]
        if b["atr20"] is None or not cond(bars, i):
            continue
        if direction == 1:
            sl = b["o"] - stop
            pts = -stop if b["l"] <= sl else (b["c"] - b["o"])
        else:
            sl = b["o"] + stop
            pts = -stop if b["h"] >= sl else -(b["c"] - b["o"])
        out.append(Trade(b["date"], pts, name))
    return out


def describe(ts: list[Trade]) -> tuple[float, float, float, int]:
    p = [t.points for t in ts]
    w = [x for x in p if x > 0]
    l = [x for x in p if x <= 0]
    return (st.mean(p), len(w) / len(p) * 100,
            st.mean(l) if l else 0.0, len(p))


# Each entry is (label, predicate, direction). Predicates read yesterday's bar
# and today's open only -- nothing that would not be known at 09:30.
CONDS = [
    ("prior close top 20% of range", lambda B, i: B[i-1]["clv"] >= 0.8, 1),
    ("prior close bot 20% of range", lambda B, i: B[i-1]["clv"] <= 0.2, 1),
    ("prior close bot 20%, short", lambda B, i: B[i-1]["clv"] <= 0.2, -1),
    ("gap down 0.25-1%", lambda B, i: -0.010 <= B[i]["gap"] <= -0.0025, 1),
    ("gap down >1%", lambda B, i: B[i]["gap"] < -0.010, 1),
    ("gap up 0.25-1%", lambda B, i: 0.0025 <= B[i]["gap"] <= 0.010, 1),
    ("inside day", lambda B, i: B[i-1]["h"] < B[i-2]["h"] and B[i-1]["l"] > B[i-2]["l"], 1),
    ("range contraction <0.7 ATR", lambda B, i: B[i-1]["range"] < 0.7 * B[i]["atr20"], 1),
    ("range expansion >1.5 ATR", lambda B, i: B[i-1]["range"] > 1.5 * B[i]["atr20"], 1),
    ("above 20 & 50 SMA", lambda B, i: B[i]["o"] > B[i]["sma20"] > B[i]["sma50"], 1),
    ("below 20 & 50 SMA", lambda B, i: B[i]["o"] < B[i]["sma20"] < B[i]["sma50"], 1),
    ("below 20&50 SMA, short", lambda B, i: B[i]["o"] < B[i]["sma20"] < B[i]["sma50"], -1),
    ("2 down days, uptrend", lambda B, i: B[i]["dn_streak"] >= 2 and B[i]["o"] > B[i]["sma50"], 1),
    ("3 down days", lambda B, i: B[i]["dn_streak"] >= 3, 1),
    ("3 up days", lambda B, i: B[i]["up_streak"] >= 3, 1),
    ("3 up days, short", lambda B, i: B[i]["up_streak"] >= 3, -1),
    ("open above prior high", lambda B, i: B[i]["o"] > B[i-1]["h"], 1),
    ("open below prior low", lambda B, i: B[i]["o"] < B[i-1]["l"], 1),
    ("prior day down >1%", lambda B, i: B[i-1]["ret"] < -0.010, 1),
    ("prior day up >1%", lambda B, i: B[i-1]["ret"] > 0.010, 1),
    ("Monday", lambda B, i: B[i]["dow"] == 0, 1),
    ("Tuesday", lambda B, i: B[i]["dow"] == 1, 1),
    ("Thursday", lambda B, i: B[i]["dow"] == 3, 1),
    ("Friday", lambda B, i: B[i]["dow"] == 4, 1),
    ("low vol (ATR < 0.8x)", lambda B, i: B[i-1]["range"] < 0.8 * B[i]["atr20"], 1),
    ("gap down + uptrend", lambda B, i: B[i]["gap"] <= -0.0025 and B[i]["o"] > B[i]["sma50"], 1),
    ("gap down + contraction", lambda B, i: B[i]["gap"] <= -0.0025 and B[i-1]["range"] < B[i]["atr20"], 1),
    ("weak close + gap down", lambda B, i: B[i-1]["clv"] <= 0.35 and B[i]["gap"] <= -0.002, 1),
    ("strong close + gap down", lambda B, i: B[i-1]["clv"] >= 0.65 and B[i]["gap"] <= -0.002, 1),
    ("unconditional long", lambda B, i: True, 1),
]


def main() -> None:
    bars = load_panel(sys.argv[1] if len(sys.argv) > 1
                      else "results/daily_panel.csv")
    build_context(bars)
    print(f"{len(bars)} bars  {bars[0]['date']} -> {bars[-1]['date']}  "
          f"stop {STOP_PTS:.0f}pt, flat at close\n")

    results = []
    for label, cond, d in CONDS:
        ts = run(bars, cond, d, name=label)
        if len(ts) < 150:
            continue
        avg, wr, avgl, n = describe(ts)
        # Split in half to see whether the condition is stable or a period
        # artefact; a rule that only worked before 2013 is not a rule.
        mid = bars[len(bars) // 2]["date"]
        h1 = [t.points for t in ts if t.date < mid]
        h2 = [t.points for t in ts if t.date >= mid]
        results.append({
            "label": label, "dir": d, "n": n, "wr": wr, "avg": avg,
            "avgl": avgl, "trades": ts,
            "h1": st.mean(h1) if h1 else 0.0,
            "h2": st.mean(h2) if h2 else 0.0,
        })

    print("=" * 96)
    print("ENTRY CONDITION SCREEN  (ranked by average points per trade)")
    print("=" * 96)
    print(f"{'condition':<30} {'dir':>4} {'n':>5} {'WR':>6} {'avg':>7} "
          f"{'avgL':>7} {'1st half':>9} {'2nd half':>9}")
    for r in sorted(results, key=lambda x: -x["avg"]):
        d = "L" if r["dir"] == 1 else "S"
        print(f"{r['label']:<30} {d:>4} {r['n']:5d} {r['wr']:5.1f}% "
              f"{r['avg']:+7.2f} {r['avgl']:+7.1f} {r['h1']:+9.2f} {r['h2']:+9.2f}")

    # Only conditions that earn in both halves are worth simulating.
    keep = [r for r in results
            if r["avg"] > 0.5 and r["h1"] > 0 and r["h2"] > 0]
    print(f"\n{len(keep)} conditions positive in both halves -> barrier sim\n")

    orig = list(TIERS)
    TIERS.clear()
    TIERS.extend([(0.0, 4.0, 240.0)])
    print(f"{'condition':<30} {'pass':>7} {'bust':>7}")
    sims = []
    for r in sorted(keep, key=lambda x: -x["avg"]):
        s = simulate(r["trades"], window=80, day_stop_profit=1450.0)
        sims.append((r, s))
        print(f"{r['label']:<30} {s.pass_rate:6.1f}% {s.bust_rate:6.1f}%")

    if len(sims) >= 2:
        top = [r for r, _ in sims[:4]]
        combo = merge(*[r["trades"] for r in top])
        s = simulate(combo, window=80, day_stop_profit=1450.0)
        print(f"\ntop {len(top)} combined ({len(combo)} trades): "
              f"pass {s.pass_rate:.1f}%  bust {s.bust_rate:.1f}%")

    TIERS.clear()
    TIERS.extend(orig)


if __name__ == "__main__":
    main()
