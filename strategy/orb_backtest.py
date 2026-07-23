"""
5-minute Opening Range Breakout (ORB) backtester
=================================================

Faithful replication of the strategy from:

    Zarattini, C. & Aziz, A. (2023).
    "Can Day Trading Really Be Profitable? Evidence of Sustainable Long-term
     Profits from Opening Range Breakout (ORB) Day Trading Strategy vs.
     Benchmark in the US Stock Market."
    SSRN 4416622.

The paper trades QQQ (Nasdaq-100 ETF) with leverage. Here the *same rules* are
applied to the **Nasdaq-100 (NQ)** via OANDA's NAS100 1-minute index data, which
tracks NQ futures/cash NDX very closely intraday. This standalone engine mirrors,
one-to-one, the logic in `quantconnect_nq_orb.py` so results are reproducible on
QuantConnect with real NQ futures data.

Rules (5-min ORB, long & short):
  * Opening range (OR) = first 5-minute candle of the RTH cash session
    (09:30-09:35 America/New_York), built from the 1-min bars 09:30..09:34.
  * Direction from the OR candle:
        OR close > OR open  -> go LONG
        OR close < OR open  -> go SHORT
        OR close == OR open -> no trade (doji)
  * Entry at the OPEN of the 2nd 5-min candle (09:35 ET).
  * Stop loss at the opposite extreme of the OR:
        long  -> OR low        short -> OR high
    R (risk per unit) = |entry - stop|.  If R == 0 -> skip.
  * Profit target = 10R.  Otherwise exit at the RTH close (16:00 ET, i.e. the
    close of the last <=15:59 bar).
  * One trade per day maximum.
  * Position sizing (paper's model):
        units = min( risk_pct * Equity / R ,  max_leverage * Equity / EntryPrice )
    risk_pct = 1%, max_leverage = 4x.  Equity compounds.
  * Costs: `cost_bps_per_side` applied to entry and exit fills (slippage+commission).

Author: research repo strongchicken04/sp500-futures-research
"""

from __future__ import annotations

import glob
import json
import os
from dataclasses import dataclass, asdict, field

import numpy as np
import pandas as pd

ET = "America/New_York"

# Minutes-since-ET-midnight helpers
OR_START = 9 * 60 + 30      # 570  -> 09:30
OR_LAST = 9 * 60 + 34       # 574  -> 09:34 (last OR minute)
ENTRY_MIN = 9 * 60 + 35     # 575  -> 09:35 (entry bar open)
RTH_LAST = 15 * 60 + 59     # 959  -> 15:59 (last bar we exit on for EOD)


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
@dataclass
class Config:
    data_dir: str
    start_year: int = 2016
    end_year: int = 2020
    start_equity: float = 100_000.0
    risk_pct: float = 0.01           # 1% risk per trade
    max_leverage: float = 4.0        # Reg-T PDT intraday cap (paper)
    target_R: float = 10.0           # 10R profit target
    cost_bps_per_side: float = 1.5   # slippage + commission per side, in bps of price
    allow_long: bool = True
    allow_short: bool = True


# --------------------------------------------------------------------------- #
# Data loading
# --------------------------------------------------------------------------- #
_LOAD_CACHE: dict = {}


def load_rth_1min(cfg: Config) -> pd.DataFrame:
    """Load OANDA NAS100 1-min CSVs, convert UTC->ET, keep RTH bars only."""
    key = (cfg.data_dir, cfg.start_year, cfg.end_year)
    if key in _LOAD_CACHE:
        return _LOAD_CACHE[key]
    files = []
    for year in range(cfg.start_year, cfg.end_year + 1):
        files += glob.glob(os.path.join(cfg.data_dir, str(year),
                                        f"oanda-NAS100_USD-{year}-*.csv"))
    if not files:
        raise FileNotFoundError(f"No NAS100 CSVs found under {cfg.data_dir} "
                                f"for {cfg.start_year}-{cfg.end_year}")
    frames = [pd.read_csv(f) for f in sorted(files)]
    df = pd.concat(frames, ignore_index=True)
    df["time"] = pd.to_datetime(df["time"], utc=True)
    et = df["time"].dt.tz_convert(ET)
    df["date"] = et.dt.strftime("%Y-%m-%d")
    df["etmin"] = et.dt.hour * 60 + et.dt.minute
    # Regular Trading Hours only: 09:30 (570) .. 16:00 (960)
    df = df[(df["etmin"] >= OR_START) & (df["etmin"] <= 16 * 60)].copy()
    df.sort_values("time", inplace=True)
    out = df[["date", "etmin", "open", "high", "low", "close", "volume"]]
    _LOAD_CACHE[key] = out
    return out


# --------------------------------------------------------------------------- #
# Backtest engine
# --------------------------------------------------------------------------- #
def run_backtest(cfg: Config, allowed_dates=None, risk_by_date=None):
    """allowed_dates: optional set of 'YYYY-MM-DD' strings; if given, only those
    days are traded (used by the regime filter).
    risk_by_date: optional {date: risk_fraction} overriding cfg.risk_pct per day
    (used by volatility-targeted sizing)."""
    df = load_rth_1min(cfg)
    equity = cfg.start_equity
    trades = []
    daily_equity = []  # (date, equity_at_close)

    cost = cfg.cost_bps_per_side / 1e4

    for date, day in df.groupby("date", sort=True):
        if allowed_dates is not None and date not in allowed_dates:
            daily_equity.append((date, equity))
            continue
        bars = day.set_index("etmin")
        # Need the OR open bar (570), an OR close bar (574) and the entry bar (575)
        if OR_START not in bars.index or ENTRY_MIN not in bars.index:
            daily_equity.append((date, equity))
            continue
        or_bars = bars.loc[(bars.index >= OR_START) & (bars.index <= OR_LAST)]
        if OR_LAST not in or_bars.index:
            daily_equity.append((date, equity))
            continue

        or_open = float(bars.loc[OR_START, "open"])
        or_close = float(or_bars.loc[OR_LAST, "close"])
        or_high = float(or_bars["high"].max())
        or_low = float(or_bars["low"].min())

        # Direction from the opening 5-min candle
        if or_close > or_open:
            direction = 1          # long
        elif or_close < or_open:
            direction = -1         # short
        else:
            daily_equity.append((date, equity))
            continue               # doji -> no trade
        if direction == 1 and not cfg.allow_long:
            daily_equity.append((date, equity)); continue
        if direction == -1 and not cfg.allow_short:
            daily_equity.append((date, equity)); continue

        entry = float(bars.loc[ENTRY_MIN, "open"])
        stop = or_low if direction == 1 else or_high
        R = (entry - stop) if direction == 1 else (stop - entry)
        if R <= 0:
            daily_equity.append((date, equity))
            continue               # entry already past stop -> skip

        target = entry + direction * cfg.target_R * R

        # Position sizing: risk-cap vs leverage-cap. risk_by_date lets a caller
        # override the per-trade risk fraction per day (e.g. volatility targeting).
        rp = risk_by_date.get(date, cfg.risk_pct) if risk_by_date else cfg.risk_pct
        units_risk = rp * equity / R
        units_lev = cfg.max_leverage * equity / entry
        units = min(units_risk, units_lev)

        # Walk the intraday bars from entry (inclusive) to RTH close
        trade_bars = bars.loc[(bars.index >= ENTRY_MIN) & (bars.index <= RTH_LAST)]
        exit_price = None
        exit_reason = None
        for etmin, b in trade_bars.iterrows():
            hi, lo = float(b["high"]), float(b["low"])
            if direction == 1:
                # conservative: check stop before target within the same bar
                if lo <= stop:
                    exit_price = min(float(b["open"]), stop)  # gap-through fills at open
                    exit_reason = "stop"; break
                if hi >= target:
                    exit_price = max(float(b["open"]), target)
                    exit_reason = "target"; break
            else:
                if hi >= stop:
                    exit_price = max(float(b["open"]), stop)
                    exit_reason = "stop"; break
                if lo <= target:
                    exit_price = min(float(b["open"]), target)
                    exit_reason = "target"; break
        if exit_price is None:
            exit_price = float(trade_bars.iloc[-1]["close"])
            exit_reason = "eod"

        # Apply costs (slippage+commission) to both fills, against the trader
        entry_fill = entry * (1 + direction * cost)
        exit_fill = exit_price * (1 - direction * cost)
        pnl_points = direction * (exit_fill - entry_fill)
        pnl_cash = units * pnl_points
        realized_R = direction * (exit_price - entry) / R  # gross R (pre-cost)

        equity += pnl_cash
        trades.append({
            "date": date, "direction": direction, "entry": round(entry, 2),
            "stop": round(stop, 2), "target": round(target, 2),
            "R_points": round(R, 2), "exit": round(exit_price, 2),
            "exit_reason": exit_reason, "units": round(units, 2),
            "pnl_cash": round(pnl_cash, 2), "realized_R": round(realized_R, 3),
            "ret_pct": round(pnl_cash / (equity - pnl_cash) * 100, 4),
            "equity": round(equity, 2),
            "lev_capped": units_lev < units_risk,
        })
        daily_equity.append((date, equity))

    trades_df = pd.DataFrame(trades)
    eq_df = pd.DataFrame(daily_equity, columns=["date", "equity"])
    eq_df["date"] = pd.to_datetime(eq_df["date"])
    return trades_df, eq_df, df


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #
def buy_hold_metrics(raw_1min: pd.DataFrame):
    """Buy & hold NAS100 over the tested window using RTH closes."""
    closes = raw_1min.groupby("date")["close"].last()
    closes.index = pd.to_datetime(closes.index)
    closes = closes.sort_index()
    daily_ret = closes.pct_change().dropna()
    total = closes.iloc[-1] / closes.iloc[0] - 1
    years = (closes.index[-1] - closes.index[0]).days / 365.25
    cagr = (1 + total) ** (1 / years) - 1 if years > 0 else np.nan
    sharpe = daily_ret.mean() / daily_ret.std() * np.sqrt(252) if daily_ret.std() else np.nan
    cummax = closes.cummax()
    maxdd = ((closes - cummax) / cummax).min()
    return {"total_return_pct": total * 100, "cagr_pct": cagr * 100,
            "sharpe": sharpe, "max_drawdown_pct": maxdd * 100, "years": years}


def compute_metrics(cfg: Config, trades_df: pd.DataFrame, eq_df: pd.DataFrame,
                    raw_1min: pd.DataFrame) -> dict:
    m: dict = {}
    n = len(trades_df)
    m["config"] = asdict(cfg)
    m["n_trades"] = n
    if n == 0:
        return m

    wins = trades_df[trades_df["pnl_cash"] > 0]
    losses = trades_df[trades_df["pnl_cash"] <= 0]
    m["n_wins"] = len(wins)
    m["n_losses"] = len(losses)
    m["win_rate_pct"] = len(wins) / n * 100
    m["exit_breakdown"] = trades_df["exit_reason"].value_counts().to_dict()
    m["long_trades"] = int((trades_df["direction"] == 1).sum())
    m["short_trades"] = int((trades_df["direction"] == -1).sum())
    m["lev_capped_trades"] = int(trades_df["lev_capped"].sum())

    # R statistics (gross, instrument-agnostic edge)
    m["avg_R"] = trades_df["realized_R"].mean()
    m["expectancy_R"] = trades_df["realized_R"].mean()
    m["avg_win_R"] = wins["realized_R"].mean() if len(wins) else 0.0
    m["avg_loss_R"] = losses["realized_R"].mean() if len(losses) else 0.0
    gross_win = wins["pnl_cash"].sum()
    gross_loss = -losses["pnl_cash"].sum()
    m["profit_factor"] = gross_win / gross_loss if gross_loss > 0 else np.inf

    # Equity-curve performance
    start_eq = cfg.start_equity
    end_eq = eq_df["equity"].iloc[-1]
    total_ret = end_eq / start_eq - 1
    days = (eq_df["date"].iloc[-1] - eq_df["date"].iloc[0]).days
    years = days / 365.25
    m["start_equity"] = start_eq
    m["end_equity"] = end_eq
    m["total_return_pct"] = total_ret * 100
    m["cagr_pct"] = ((end_eq / start_eq) ** (1 / years) - 1) * 100 if years > 0 else np.nan
    m["years"] = years

    daily_ret = eq_df.set_index("date")["equity"].pct_change().dropna()
    ann_vol = daily_ret.std() * np.sqrt(252)
    m["ann_vol_pct"] = ann_vol * 100
    m["sharpe"] = (daily_ret.mean() / daily_ret.std() * np.sqrt(252)
                   if daily_ret.std() else np.nan)
    downside = daily_ret[daily_ret < 0].std()
    m["sortino"] = (daily_ret.mean() / downside * np.sqrt(252)
                    if downside and downside == downside else np.nan)
    cummax = eq_df["equity"].cummax()
    dd = (eq_df["equity"] - cummax) / cummax
    m["max_drawdown_pct"] = dd.min() * 100
    m["calmar"] = (m["cagr_pct"] / abs(m["max_drawdown_pct"])
                   if m["max_drawdown_pct"] else np.nan)

    # Per-year breakdown
    ty = trades_df.copy()
    ty["year"] = pd.to_datetime(ty["date"]).dt.year
    yearly = {}
    for yr, g in ty.groupby("year"):
        eq_start = g["equity"].iloc[0] - g["pnl_cash"].iloc[0]
        eq_end = g["equity"].iloc[-1]
        yearly[int(yr)] = {
            "trades": len(g),
            "return_pct": round((eq_end / eq_start - 1) * 100, 2),
            "win_rate_pct": round((g["pnl_cash"] > 0).mean() * 100, 1),
            "expectancy_R": round(g["realized_R"].mean(), 3),
        }
    m["yearly"] = yearly
    m["avg_trades_per_year"] = n / years if years else np.nan

    # Benchmark
    m["buy_hold"] = buy_hold_metrics(raw_1min)
    return m


def print_report(m: dict, title: str):
    print(f"\n{'='*66}\n{title}\n{'='*66}")
    if m.get("n_trades", 0) == 0:
        print("No trades."); return
    print(f"Trades: {m['n_trades']}  (long {m['long_trades']} / short {m['short_trades']})"
          f"  |  ~{m['avg_trades_per_year']:.0f}/yr")
    print(f"Win rate: {m['win_rate_pct']:.1f}%   "
          f"Expectancy: {m['expectancy_R']:+.3f}R/trade   "
          f"Profit factor: {m['profit_factor']:.2f}")
    print(f"Avg win: {m['avg_win_R']:+.2f}R   Avg loss: {m['avg_loss_R']:+.2f}R")
    print(f"Exits: {m['exit_breakdown']}")
    print(f"Leverage-capped trades: {m['lev_capped_trades']}")
    print("-" * 66)
    print(f"Total return: {m['total_return_pct']:+.1f}%   CAGR: {m['cagr_pct']:+.1f}%"
          f"   ({m['years']:.1f} yrs)")
    print(f"Ann vol: {m['ann_vol_pct']:.1f}%   Sharpe: {m['sharpe']:.2f}   "
          f"Sortino: {m['sortino']:.2f}   Calmar: {m['calmar']:.2f}")
    print(f"Max drawdown: {m['max_drawdown_pct']:.1f}%")
    bh = m["buy_hold"]
    print(f"\nBuy & Hold NAS100:  total {bh['total_return_pct']:+.1f}%   "
          f"CAGR {bh['cagr_pct']:+.1f}%   Sharpe {bh['sharpe']:.2f}   "
          f"MaxDD {bh['max_drawdown_pct']:.1f}%")
    print("\nPer-year:")
    for yr, y in m["yearly"].items():
        print(f"  {yr}:  {y['return_pct']:+7.1f}%   "
              f"win {y['win_rate_pct']:4.1f}%   "
              f"exp {y['expectancy_R']:+.3f}R   ({y['trades']} trades)")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--data-dir", required=True)
    p.add_argument("--start-year", type=int, default=2016)
    p.add_argument("--end-year", type=int, default=2020)
    p.add_argument("--cost-bps", type=float, default=1.5)
    p.add_argument("--no-short", action="store_true")
    p.add_argument("--out", default=None, help="output prefix for json/csv")
    args = p.parse_args()

    cfg = Config(data_dir=args.data_dir, start_year=args.start_year,
                 end_year=args.end_year, cost_bps_per_side=args.cost_bps,
                 allow_short=not args.no_short)
    trades_df, eq_df, raw = run_backtest(cfg)
    metrics = compute_metrics(cfg, trades_df, eq_df, raw)
    tag = f"{cfg.start_year}-{cfg.end_year}"
    print_report(metrics, f"5-min ORB on NAS100 (NQ proxy) {tag}, cost {cfg.cost_bps_per_side}bp/side")

    if args.out:
        with open(f"{args.out}_metrics_{tag}.json", "w") as f:
            json.dump(metrics, f, indent=2, default=str)
        trades_df.to_csv(f"{args.out}_trades_{tag}.csv", index=False)
        eq_df.to_csv(f"{args.out}_equity_{tag}.csv", index=False)
        print(f"\nWrote {args.out}_metrics_{tag}.json / _trades_ / _equity_")
