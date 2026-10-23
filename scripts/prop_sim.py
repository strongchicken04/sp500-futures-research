"""Barrier simulator for prop-firm challenges.

Answers the only question that matters for a challenge account:
    P(reach +TARGET before breaching the trailing -DD line, within WINDOW days)

This is a first-passage problem, not a Sharpe problem. A strategy with
mediocre expectancy but tightly bounded losses can beat a high-Sharpe
strategy that has one long losing streak in it.
"""
from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass, field


# --- Lucid Trading Flex 50K ------------------------------------------------
# Rules per support.lucidtrading.com (the only source worth trusting here;
# the affiliate blogs contradict each other and the firm).
TARGET = 3000.0
MAX_DD = 2000.0
WINDOW_DAYS = 40          # 8 weeks. Lucid publishes no time limit, so this is
                          # a self-imposed horizon -- see no_deadline sweeps.

# The trailing floor ratchets on the highest END-OF-DAY balance, then freezes.
# Once an EOD close clears $52,100 the floor locks at $50,100 forever, which
# in P&L terms means it stops climbing at +100 and the last $900 to target is
# run with the full $2,000 of room underneath.
LOCK_FLOOR_PNL = 100.0    # $50,100 relative to a $50,000 start

# Consistency gate: largest single day must be <= 50% of FINAL profit.
# It blocks the payout upgrade rather than killing the account, and
# overshooting the target relaxes it, so it is a constraint on the end state
# rather than a per-day kill switch.
CONSISTENCY_FRAC = 0.50

# Sizing tiers keyed on banked profit. Verified Pareto-optimal over 13 schemes.
# (profit_floor, dollars_per_point, daily_loss_stop)
TIERS = [
    (0.0,    4.0,  400.0),   # 2 MNQ
    (400.0,  6.0,  500.0),   # 3 MNQ
    (1000.0, 20.0, 600.0),   # 1 NQ
]


def tier_for(profit: float) -> tuple[float, float]:
    """Return (dollars_per_point, daily_loss_stop) for a given banked profit."""
    dpp, stop = TIERS[0][1], TIERS[0][2]
    for floor, d, s in TIERS:
        if profit >= floor:
            dpp, stop = d, s
    return dpp, stop


@dataclass
class Trade:
    date: str
    points: float
    strat: str = ""


@dataclass
class SimResult:
    passed: int = 0
    busted: int = 0
    timeout: int = 0
    pass_days: list[int] = field(default_factory=list)
    consistency_blocked: int = 0   # hit target but best day > 50% of profit

    @property
    def n(self) -> int:
        return self.passed + self.busted + self.timeout

    @property
    def pass_rate(self) -> float:
        return self.passed / self.n * 100 if self.n else 0.0

    @property
    def bust_rate(self) -> float:
        return self.busted / self.n * 100 if self.n else 0.0

    @property
    def median_days(self) -> float:
        if not self.pass_days:
            return float("nan")
        s = sorted(self.pass_days)
        return s[len(s) // 2]


def load_tags(path: str, *, fmt: str) -> list[Trade]:
    """Parse a QuantConnect order-tag dump into trades.

    fmt 's1'    -> S1,datetime,entry,sl,exit,reason,pnl,bars
    fmt 'combo' -> COMBO,datetime,strat,dir,entry,sl,exit,reason,pnl,bars
    """
    out: list[Trade] = []
    with open(path) as fh:
        for line in fh:
            parts = line.strip().split(",")
            if len(parts) < 7:
                continue
            try:
                if fmt == "s1":
                    date = parts[1].split(" ")[0]
                    pts = float(parts[6])
                    strat = parts[0]
                elif fmt == "combo":
                    date = parts[1].split(" ")[0]
                    pts = float(parts[8])
                    strat = parts[2]
                else:
                    raise ValueError(f"unknown fmt {fmt}")
            except (ValueError, IndexError):
                continue
            out.append(Trade(date, pts, strat))
    return out


def by_day(trades: list[Trade]) -> dict[str, list[Trade]]:
    d: dict[str, list[Trade]] = defaultdict(list)
    for t in trades:
        d[t.date].append(t)
    return d


def simulate(
    trades: list[Trade],
    *,
    target: float = TARGET,
    max_dd: float = MAX_DD,
    window: int = WINDOW_DAYS,
    lock_floor: float | None = LOCK_FLOOR_PNL,
    day_stop_profit: float | None = None,
    enforce_consistency: bool = True,
    stride: int = 1,
) -> SimResult:
    """Walk every possible WINDOW-day start and record pass/bust/timeout.

    lock_floor: the P&L level at which the trailing line stops ratcheting.
        Lucid locks the 50K floor at $50,100 (= +100 P&L) once an EOD close
        clears $52,100. Pass None to model a floor that trails forever.
    day_stop_profit: stop trading for the day once this much is banked.
        Caps a single day's share of total profit for the consistency gate.
    enforce_consistency: require best_day <= 50% of final profit to count a
        pass. The gate delays the upgrade rather than killing the account,
        so a blocked run is tracked separately from an outright failure.
    """
    days = sorted(by_day(trades).items())
    res = SimResult()

    for start in range(0, max(0, len(days) - window), stride):
        pnl = 0.0
        peak_eod = 0.0
        outcome = "timeout"
        day_n = 0
        best_day = 0.0

        for day_idx in range(start, min(start + window, len(days))):
            day_n += 1
            _, day_trades = days[day_idx]

            dd_line = peak_eod - max_dd
            if lock_floor is not None:
                dd_line = min(dd_line, lock_floor)

            day_pnl = 0.0
            dpp, day_stop = tier_for(pnl)

            for t in day_trades:
                day_pnl += t.points * dpp
                equity = pnl + day_pnl

                if equity <= dd_line:
                    outcome = "bust"
                    break
                # Hitting the target is not enough on its own: the gate also
                # needs the best day to be at most half of total profit. If it
                # is not, keep trading -- extra profit dilutes the ratio, which
                # is cheaper than the alternative of grinding out more days.
                if equity >= target:
                    best_so_far = max(best_day, day_pnl)
                    if not enforce_consistency or best_so_far <= CONSISTENCY_FRAC * equity:
                        outcome = "pass"
                        break
                if day_pnl <= -day_stop:
                    break
                if day_stop_profit is not None and day_pnl >= day_stop_profit:
                    break

            pnl += day_pnl
            best_day = max(best_day, day_pnl)
            if outcome in ("bust", "pass"):
                break
            peak_eod = max(peak_eod, pnl)

        if outcome == "pass":
            res.passed += 1
            res.pass_days.append(day_n)
        elif outcome == "bust":
            res.busted += 1
        else:
            res.timeout += 1
            if enforce_consistency and pnl >= target:
                res.consistency_blocked += 1

    return res


# Typical entry order within a day (trades carry no time): opening-range and
# overnight-level trades first, VWAP band next, then the 10:00+ signals.
# Without this, the day's order followed the order of merge() arguments and
# lifecycle results moved by up to ~25% (found 2026-10-23).
ENTRY_RANK = {"S1": 0, "ORB": 0, "YM": 0, "ONL": 0.5, "VG": 1, "VWAP": 1, "Z": 2, "RS": 3}


def merge(*trade_sets: list[Trade]) -> list[Trade]:
    """Interleave several strategies into one chronological trade stream."""
    all_t = [t for ts in trade_sets for t in ts]
    all_t.sort(key=lambda t: (t.date, ENTRY_RANK.get(t.strat, 5)))
    return all_t


def cap_concurrent(trades: list[Trade], max_per_day: int) -> list[Trade]:
    """Keep at most N trades per day, in arrival order."""
    seen: dict[str, int] = defaultdict(int)
    out = []
    for t in trades:
        if seen[t.date] < max_per_day:
            out.append(t)
            seen[t.date] += 1
    return out


def report(name: str, res: SimResult) -> str:
    return (
        f"{name:<34} pass {res.pass_rate:5.1f}%  bust {res.bust_rate:5.1f}%  "
        f"timeout {100 - res.pass_rate - res.bust_rate:5.1f}%  "
        f"n={res.n:<5} med_days={res.median_days}"
    )


def write_trades_csv(trades: list[Trade], path: str) -> None:
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["date", "strat", "points"])
        for t in trades:
            w.writerow([t.date, t.strat, f"{t.points:.2f}"])
