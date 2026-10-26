# region imports
from AlgorithmImports import *
# endregion


class NasdaqOpeningRangeBreakout(QCAlgorithm):
    """
    5-minute Opening Range Breakout (ORB) on E-mini Nasdaq-100 futures (NQ).

    Faithful replication of:
        Zarattini, C. & Aziz, A. (2023) "Can Day Trading Really Be Profitable?"
        SSRN 4416622  (5-minute ORB, long & short, 10R target).

    Rules
    -----
    * Opening range (OR) = first 5-minute candle of the equity cash session
      (09:30-09:35 America/New_York), built from the 1-min bars 09:30..09:34.
    * Direction from the OR candle:
          OR close > OR open  -> LONG
          OR close < OR open  -> SHORT
          OR close == OR open -> no trade (doji)
    * Entry: market order at the OPEN of the 2nd 5-min candle (09:35 ET).
    * Stop: opposite extreme of the OR (long -> OR low, short -> OR high).
          R = |entry - stop|.
    * Target: 10R (resting limit). Otherwise flat at the RTH close (15:59 ET).
    * One trade per day.
    * Sizing (paper): contracts = floor( min( risk% * Equity / (R * mult),
                                              maxLev * Equity / (price * mult) ) )
      risk% = 1%, maxLev = 4x.  NQ contract multiplier = $20 / point.

    NQ trades ~23h, so RTH is enforced purely by the 09:30-16:00 ET time filter;
    the futures Globex session is otherwise ignored (as in the paper).
    """

    def Initialize(self):
        self.SetStartDate(2016, 1, 1)
        self.SetEndDate(2024, 1, 1)
        self.SetCash(1_000_000)

        # ---- strategy parameters ----
        self.risk_pct = 0.01        # 1% of equity risked per trade
        self.max_leverage = 4.0     # Reg-T PDT intraday cap (paper)
        self.target_R = 10.0        # 10R profit target
        self.allow_long = True
        self.allow_short = True

        # ---- NQ continuous future, raw prices (correct for intraday levels) ----
        future = self.AddFuture(
            Futures.Indices.NASDAQ_100_E_MINI,
            resolution=Resolution.Minute,
            dataNormalizationMode=DataNormalizationMode.Raw,
            dataMappingMode=DataMappingMode.OpenInterest,
            contractDepthOffset=0,
            extendedMarketHours=True,     # get all bars; we filter RTH ourselves
        )
        future.SetFilter(0, 120)
        self.future = future
        self.cont_symbol = future.Symbol

        # ---- per-day state ----
        self._reset_day()

        # daily reset just before the cash open and forced-flat before the close
        self.Schedule.On(self.DateRules.EveryDay(self.cont_symbol),
                         self.TimeRules.At(9, 29), self._reset_day)
        self.Schedule.On(self.DateRules.EveryDay(self.cont_symbol),
                         self.TimeRules.At(15, 59), self._close_eod)

        self.SetWarmUp(timedelta(days=3))

    # ------------------------------------------------------------------ #
    def _reset_day(self):
        self.or_open = None
        self.or_high = None
        self.or_low = None
        self.or_close = None
        self.traded_today = False
        self.entry_price = None
        self.stop_price = None
        self.target_price = None
        self.entry_ticket = None
        self.stop_ticket = None
        self.target_ticket = None

    def _tradable_symbol(self):
        m = self.future.Mapped
        if m is None:
            return None
        return m

    # ------------------------------------------------------------------ #
    def OnData(self, slice: Slice):
        if self.IsWarmingUp:
            return

        t = self.Time
        minute_of_day = t.hour * 60 + t.minute

        # continuous (raw front-month) bar for signal construction
        bar = slice.Bars.get(self.cont_symbol) if slice.Bars is not None else None

        # ---- build opening range on bars delivered 09:31 .. 09:35 ----
        # (bar delivered at 09:31 covers [09:30,09:31) and carries the 09:30 open)
        if bar is not None and 9 * 60 + 31 <= minute_of_day <= 9 * 60 + 35:
            if self.or_open is None:
                self.or_open = bar.Open
                self.or_high = bar.High
                self.or_low = bar.Low
            else:
                self.or_high = max(self.or_high, bar.High)
                self.or_low = min(self.or_low, bar.Low)
            self.or_close = bar.Close

            # OR complete at 09:35 -> decide & enter
            if minute_of_day == 9 * 60 + 35 and not self.traded_today:
                self._try_enter()

    # ------------------------------------------------------------------ #
    def _try_enter(self):
        self.traded_today = True
        if self.or_open is None or self.or_close is None:
            return

        if self.or_close > self.or_open:
            direction = 1
        elif self.or_close < self.or_open:
            direction = -1
        else:
            return  # doji -> no trade
        if direction == 1 and not self.allow_long:
            return
        if direction == -1 and not self.allow_short:
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
        qty_risk = self.risk_pct * equity / (R * mult)
        qty_lev = self.max_leverage * equity / (price * mult)
        qty = int(min(qty_risk, qty_lev))
        if qty < 1:
            return

        self.entry_price = price
        self.stop_price = stop
        self.target_price = price + direction * self.target_R * R

        # Enter. In backtesting a MarketOrder fills SYNCHRONOUSLY, so we arm the
        # protective stop + target orders here (right after the fill) rather than
        # in OnOrderEvent -- OnOrderEvent for the entry fill runs *before* the
        # assignment below completes, which would leave the trade unprotected.
        self.entry_ticket = self.MarketOrder(symbol, direction * qty)
        filled = self.entry_ticket.QuantityFilled
        signed = filled if filled != 0 else direction * qty  # backtest fills fully
        self.stop_ticket = self.StopMarketOrder(symbol, -signed, self.stop_price)
        self.target_ticket = self.LimitOrder(symbol, -signed, self.target_price)

    # ------------------------------------------------------------------ #
    def OnOrderEvent(self, orderEvent: OrderEvent):
        if orderEvent.Status != OrderStatus.Filled:
            return
        # stop or target filled -> cancel the sibling (one-cancels-other)
        if self.stop_ticket is not None and orderEvent.OrderId == self.stop_ticket.OrderId:
            if self.target_ticket is not None and self.target_ticket.Status not in (
                    OrderStatus.Filled, OrderStatus.Canceled, OrderStatus.Invalid):
                self.target_ticket.Cancel()
            return
        if self.target_ticket is not None and orderEvent.OrderId == self.target_ticket.OrderId:
            if self.stop_ticket is not None and self.stop_ticket.Status not in (
                    OrderStatus.Filled, OrderStatus.Canceled, OrderStatus.Invalid):
                self.stop_ticket.Cancel()
            return

    # ------------------------------------------------------------------ #
    def _close_eod(self):
        # cancel any resting child orders and flatten before the cash close
        for tk in (self.stop_ticket, self.target_ticket, self.entry_ticket):
            if tk is not None and tk.Status not in (OrderStatus.Filled,
                                                    OrderStatus.Canceled,
                                                    OrderStatus.Invalid):
                tk.Cancel()
        if self.Portfolio.Invested:
            self.Liquidate()
