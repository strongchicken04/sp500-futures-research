# Data

## Primary — QuantConnect NQ futures
The definitive backtest uses **QuantConnect's own NQ E-mini minute data** (cloud).
Nothing to download locally; run `strategy/quantconnect/main.py` in a QC project.
Raw statistics/equity of the run are saved under [`../results/`](../results/).

## Supporting — NAS100 1-minute (NQ proxy) for the standalone engine
The Python engine (`strategy/orb_backtest.py`) uses **OANDA NAS100 1-minute bars**
(the Nasdaq-100 index CFD, a close intraday proxy for NQ), sourced from the public
GPL-3.0 dataset **[FutureSharks/financial-data](https://github.com/FutureSharks/financial-data)**.
Coverage: **2005-01 → 2020-05**. Timestamps are **UTC** (verified: tick-volume
jumps exactly at 13:30/14:30 UTC = 09:30 ET cash open); the engine converts to
America/New_York and keeps RTH only.

The raw CSVs (~200 MB) are **not committed**. Fetch them with:

```bash
git clone --filter=blob:none --no-checkout https://github.com/FutureSharks/financial-data.git
cd financial-data
git checkout HEAD -- pyfinancialdata/data/currencies/oanda/NAS100_USD/
# -> pass .../oanda/NAS100_USD as --data-dir to the backtester
```

### Proxy caveats
- OANDA NAS100 CFD ≈ Nasdaq-100 cash/NQ intraday, but is not the NQ contract:
  no true contract roll, CFD (not exchange) prices, tick-volume (not real volume).
- Good enough for an OHLC-driven ORB study; the QuantConnect run on real NQ is the
  authoritative result. The two agree closely (win rate ~24%, profit factor ~1.05).
