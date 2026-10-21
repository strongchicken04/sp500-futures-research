"""Win-streak arithmetic for the evaluation: one bet a day, win W or lose L.

The account needs +$3,000 with the best day at most half the profit and at
most $1,450 a day, under a $2,000 end-of-day trailing drawdown (locks at
+$100 after +$2,100). A stop must sit inside the $2,000 line, so L <= $1,950.
For a planned streak of N winning days, W = $3,000 / N. The win rate is the
random-walk rate for the bracket, L / (W + L), plus an edge of 0, 5 or 10
percentage points. Printed: p^N (N straight wins), the pass rate when the
account is allowed to absorb losses on the way, and median days to pass.
"""
from __future__ import annotations

import sys

sys.path.insert(0, "scripts")
from payoff_shape import run  # noqa: E402


def main():
    print(f"{'streak':>6} {'win $':>6} {'loss $':>7} {'RR':>6} {'edge':>5} {'WR':>6} {'p^N':>6} {'pass':>6} {'days':>5}")
    for n in (3, 4, 5, 6):
        w = 3000.0 / n
        for L in (2 * w, min(1950.0, 3.3 * w), 1950.0):
            if L > 1950:
                continue
            for e in (0.0, 0.05, 0.10):
                p = L / (w + L) + e
                if p >= 1:
                    continue
                ev = p * w - (1 - p) * L
                r = run(w, L, ev, trials=30000)
                print(f"{n:6} {w:6.0f} {L:7.0f}  1:{L/w:3.1f} {e*100:+4.0f}pp {p*100:5.1f}% {p**n*100:5.1f}% {r[1]:5.1f}% {r[3]:5}")
        print()


if __name__ == "__main__":
    main()
