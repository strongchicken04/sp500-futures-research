"""Which payoff shape passes a Lucid evaluation fastest and most often?

Pure rules arithmetic, no market data: one bet per day that wins W with
probability p or loses L, with p chosen so the bet has a given expectancy.
Rules as on the account: +$3,000 target, end-of-day trailing drawdown of
$2,000 that locks at +$100 once an end-of-day balance clears +$2,100, best
day at most 50% of total profit, at most $1,450 profit per day. A loss that
takes the balance through the line busts the account during the day.
"""
from __future__ import annotations

import random
import sys


def run(W, L, ev, trials=40000, max_days=400, seed=1):
    p = (L + ev) / (W + L)                 # p*W - (1-p)*L = ev
    if not 0 < p < 1:
        return None
    rng = random.Random(seed)
    passed = bust = 0
    days_pass = []
    for _ in range(trials):
        e = hwm = best = 0.0
        line, locked = -2000.0, False
        for d in range(1, max_days + 1):
            x = W if rng.random() < p else -L
            if e + x <= line:
                bust += 1
                break
            e += x
            best = max(best, x)
            if not locked:
                hwm = max(hwm, e)
                line = hwm - 2000.0
                if hwm >= 2100.0:
                    line, locked = 100.0, True
            if e >= 3000.0 and best <= 0.5 * e:
                passed += 1
                days_pass.append(d)
                break
    days_pass.sort()
    med = days_pass[len(days_pass) // 2] if days_pass else 0
    return p, passed / trials * 100, bust / trials * 100, med


def main():
    ev = float(sys.argv[1]) if len(sys.argv) > 1 else 0.0
    print(f"expectancy per day ${ev:+.0f}")
    print(f"{'win $':>6} {'loss $':>7} {'R:R':>6} {'winrate':>8} {'pass':>6} {'bust':>6} {'days':>5}")
    for W, L in [(250, 750), (300, 1500), (500, 1500), (500, 1000), (750, 1500), (1000, 1900),
                 (500, 500), (750, 750), (1000, 1000), (1450, 1450),
                 (750, 250), (1000, 333), (1450, 500), (1450, 300), (1450, 150)]:
        r = run(W, L, ev)
        if r is None:
            continue
        p, ps, bs, md = r
        print(f"{W:6} {L:7} {W/L:6.2f} {p*100:7.1f}% {ps:5.1f}% {bs:5.1f}% {md:5}")


if __name__ == "__main__":
    main()
