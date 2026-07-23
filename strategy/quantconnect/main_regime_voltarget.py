# region imports
from AlgorithmImports import *
import numpy as np
from collections import deque
# endregion

OR_START = 9 * 60 + 30   # 09:30 ET, in minutes-since-midnight


class NasdaqRegimeVolTargetORB(QCAlgorithm):
    """
    Regime-FILTERED + VOLATILITY-TARGETED 5-minute ORB on NQ E-mini futures.

    Same mechanical 5-min ORB as `main.py` (breakout, long+short, 10R target,
    1% risk / 4x cap) but only TAKES the trade on days whose regime is
    favourable. Filter thresholds were fit on NAS100 2005-2015 and frozen:

        favourable = ( rvol20 > 0.156                # 20d realised vol (ann.)
                       OR |gap|  > 0.0030 )           # session gap vs prev close
                     AND trend50 <= 0.0406            # not a strong 50d uptrend

    All features use only information available at the 09:35 ET entry.
    The 2020-2024 portion of this backtest is out-of-sample vs the fit period.
    """

    def Initialize(self):
        self.SetStartDate(2016, 1, 1)
        self.SetEndDate(2024, 1, 1)
        self.SetCash(1_000_000)

        self.risk_pct = 0.01
        self.max_leverage = 4.0
        self.target_R = 10.0
        # volatility targeting: risk_t = clip(vt_k / rvol20, vt_lo, vt_hi)
        self.vt_k = 0.001
        self.vt_lo = 0.002
        self.vt_hi = 0.012

        # frozen regime thresholds (fit on NAS100 2005-2015)
        self.f_vol = 0.156
        self.f_gap = 0.0030
        self.f_up = 0.0406

        future = self.AddFuture(
            Futures.Indices.NASDAQ100EMini, resolution=Resolution.Minute,
            dataNormalizationMode=DataNormalizationMode.Raw,
            dataMappingMode=DataMappingMode.OpenInterest,
            contractDepthOffset=0, extendedMarketHours=True)
        future.SetFilter(0, 120)
        self.future = future
        self.cont_symbol = future.Symbol

        # rolling daily RTH closes for regime features
        self.daily_closes = deque(maxlen=70)
        self.today_close = None
        self.last_date = None
        self.cur_rvol20 = None

        self._reset_day()
        self.Schedule.On(self.DateRules.EveryDay(self.cont_symbol),
                         self.TimeRules.At(9, 29), self._reset_day)
        self.Schedule.On(self.DateRules.EveryDay(self.cont_symbol),
                         self.TimeRules.At(15, 59), self._close_eod)
        self.SetWarmUp(timedelta(days=90))

    # ------------------------------------------------------------------ #
    def _reset_day(self):
        self.or_open = self.or_high = self.or_low = self.or_close = None
        self.traded_today = False
        self.entry_price = self.stop_price = self.target_price = None
        self.entry_ticket = self.stop_ticket = self.target_ticket = None

    def _tradable_symbol(self):
        return self.future.Mapped

    # ------------------------------------------------------------------ #
    def OnData(self, slice: Slice):
        t = self.Time
        cur_date = t.date()
        bar = slice.Bars.get(self.cont_symbol) if slice.Bars is not None else None
        minute_of_day = t.hour * 60 + t.minute

        # ---- maintain rolling daily RTH close series (also during warmup) ----
        if self.last_date is None:
            self.last_date = cur_date
        if cur_date != self.last_date:
            if self.today_close is not None:
                self.daily_closes.append(self.today_close)
            self.today_close = None
            self.last_date = cur_date
        if bar is not None and OR_START <= minute_of_day <= 16 * 60:
            self.today_close = bar.Close

        if self.IsWarmingUp:
            return

        # ---- opening range (bars delivered 09:31..09:35) ----
        if bar is not None and 9 * 60 + 31 <= minute_of_day <= 9 * 60 + 35:
            if self.or_open is None:
                self.or_open, self.or_high, self.or_low = bar.Open, bar.High, bar.Low
            else:
                self.or_high = max(self.or_high, bar.High)
                self.or_low = min(self.or_low, bar.Low)
            self.or_close = bar.Close
            if minute_of_day == 9 * 60 + 35 and not self.traded_today:
                self._try_enter()

    # ------------------------------------------------------------------ #
    def _regime_ok(self) -> bool:
        closes = list(self.daily_closes)
        if len(closes) < 51:
            return False
        prev_close = closes[-1]
        arr = np.array(closes, dtype=float)
        rets = np.diff(arr) / arr[:-1]
        rvol20 = float(np.std(rets[-20:], ddof=1)) * np.sqrt(252)
        sma50 = float(np.mean(arr[-50:]))
        gap = self.or_open / prev_close - 1.0
        trend50 = prev_close / sma50 - 1.0
        self.cur_rvol20 = rvol20
        return ((rvol20 > self.f_vol) or (abs(gap) > self.f_gap)) and (trend50 <= self.f_up)

    def _try_enter(self):
        self.traded_today = True
        if self.or_open is None or self.or_close is None:
            return
        if not self._regime_ok():
            return  # unfavourable regime -> stand aside

        if self.or_close > self.or_open:
            direction = 1
        elif self.or_close < self.or_open:
            direction = -1
        else:
            return

        symbol = self._tradable_symbol()
        if symbol is None or symbol not in self.Securities:
            return
        sec = self.Securities[symbol]
        price = sec.Price
        if price <= 0:
            return
        stop = self.or_low if direction == 1 else self.or_high
        R = (price - stop) if direction == 1 else (stop - price)
        if R <= 0:
            return
        mult = sec.SymbolProperties.ContractMultiplier
        equity = self.Portfolio.TotalPortfolioValue
        rp = min(max(self.vt_k / self.cur_rvol20, self.vt_lo), self.vt_hi)  # vol target
        qty = int(min(rp * equity / (R * mult),
                      self.max_leverage * equity / (price * mult)))
        if qty < 1:
            return

        self.entry_price, self.stop_price = price, stop
        self.target_price = price + direction * self.target_R * R
        self.entry_ticket = self.MarketOrder(symbol, direction * qty)
        filled = self.entry_ticket.QuantityFilled
        signed = filled if filled != 0 else direction * qty
        self.stop_ticket = self.StopMarketOrder(symbol, -signed, self.stop_price)
        self.target_ticket = self.LimitOrder(symbol, -signed, self.target_price)

    # ------------------------------------------------------------------ #
    def OnOrderEvent(self, orderEvent: OrderEvent):
        if orderEvent.Status != OrderStatus.Filled:
            return
        if self.stop_ticket is not None and orderEvent.OrderId == self.stop_ticket.OrderId:
            if self.target_ticket is not None and self.target_ticket.Status not in (
                    OrderStatus.Filled, OrderStatus.Canceled, OrderStatus.Invalid):
                self.target_ticket.Cancel()
        elif self.target_ticket is not None and orderEvent.OrderId == self.target_ticket.OrderId:
            if self.stop_ticket is not None and self.stop_ticket.Status not in (
                    OrderStatus.Filled, OrderStatus.Canceled, OrderStatus.Invalid):
                self.stop_ticket.Cancel()

    # ------------------------------------------------------------------ #
    def _close_eod(self):
        for tk in (self.stop_ticket, self.target_ticket, self.entry_ticket):
            if tk is not None and tk.Status not in (OrderStatus.Filled,
                                                    OrderStatus.Canceled, OrderStatus.Invalid):
                tk.Cancel()
        if self.Portfolio.Invested:
            self.Liquidate()
