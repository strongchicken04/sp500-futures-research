# region imports
from AlgorithmImports import *
import numpy as np
from collections import deque
# endregion

OR_START = 9 * 60 + 30   # 09:30 ET


class NasdaqFinalORB(QCAlgorithm):
    """
    FINAL 5-minute ORB on NQ E-mini futures: re-fitted regime filter +
    volatility targeting + directional tilt.

    * Base: 5-min opening range breakout, entry at 09:35 ET, stop at the opposite
      OR extreme, 10R target else flat at 15:59 ET.
    * Re-fit filter (thresholds fit on real NQ 2009-2019):
          trade only if  |gap| > 0.0033  OR  rvol20 < 0.122
    * Directional tilt: on gap-DOWN days (gap < -0.0033) take SHORT breakouts only
      (skip long signals) -- shorts dominate on gap-down days.
    * Volatility targeting: risk_t = clip(0.001 / rvol20, 0.2%, 1.2%), capped at 4x.

    All features use only info available at the 09:35 ET entry. 2020-2025 is
    out-of-sample vs the filter fit.
    """

    def Initialize(self):
        self.SetStartDate(2016, 1, 1)
        self.SetEndDate(2025, 7, 1)
        self.SetCash(1_000_000)

        self.max_leverage = 4.0
        self.target_R = 10.0
        # re-fit filter thresholds
        self.f_gap = 0.0033
        self.f_vlo = 0.122
        # vol targeting
        self.vt_k, self.vt_lo, self.vt_hi = 0.001, 0.002, 0.012

        future = self.AddFuture(
            Futures.Indices.NASDAQ100EMini, resolution=Resolution.Minute,
            dataNormalizationMode=DataNormalizationMode.Raw,
            dataMappingMode=DataMappingMode.OpenInterest,
            contractDepthOffset=0, extendedMarketHours=True)
        future.SetFilter(0, 120)
        self.future = future
        self.cont_symbol = future.Symbol

        self.daily_closes = deque(maxlen=70)
        self.today_close = None
        self.last_date = None
        self.cur_gap = None
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

    # ------------------------------------------------------------------ #
    def OnData(self, slice: Slice):
        t = self.Time
        cur_date = t.date()
        mod = t.hour * 60 + t.minute
        bar = slice.Bars.get(self.cont_symbol) if slice.Bars is not None else None

        if self.last_date is None:
            self.last_date = cur_date
        if cur_date != self.last_date:
            if self.today_close is not None:
                self.daily_closes.append(self.today_close)
            self.today_close = None
            self.last_date = cur_date
        if bar is not None and OR_START <= mod <= 16 * 60:
            self.today_close = bar.Close

        if self.IsWarmingUp:
            return

        if bar is not None and 9 * 60 + 31 <= mod <= 9 * 60 + 35:
            if self.or_open is None:
                self.or_open, self.or_high, self.or_low = bar.Open, bar.High, bar.Low
            else:
                self.or_high = max(self.or_high, bar.High)
                self.or_low = min(self.or_low, bar.Low)
            self.or_close = bar.Close
            if mod == 9 * 60 + 35 and not self.traded_today:
                self._try_enter()

    # ------------------------------------------------------------------ #
    def _compute_regime(self) -> bool:
        closes = list(self.daily_closes)
        if len(closes) < 51:
            return False
        prev_close = closes[-1]
        arr = np.array(closes, dtype=float)
        rets = np.diff(arr) / arr[:-1]
        self.cur_rvol20 = float(np.std(rets[-20:], ddof=1)) * np.sqrt(252)
        self.cur_gap = self.or_open / prev_close - 1.0
        # re-fit filter
        return (abs(self.cur_gap) > self.f_gap) or (self.cur_rvol20 < self.f_vlo)

    def _try_enter(self):
        self.traded_today = True
        if self.or_open is None or self.or_close is None:
            return
        if not self._compute_regime():
            return  # unfavourable regime -> stand aside

        if self.or_close > self.or_open:
            direction = 1
        elif self.or_close < self.or_open:
            direction = -1
        else:
            return  # doji
        # directional tilt: on gap-down days take shorts only
        if self.cur_gap < -self.f_gap and direction == 1:
            return

        symbol = self.future.Mapped
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
