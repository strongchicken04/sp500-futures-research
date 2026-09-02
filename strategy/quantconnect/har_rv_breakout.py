# region imports
from AlgorithmImports import *
from collections import deque
import math
# endregion

# HAR-RV dynamic breakout test.
#
# Daily realized variance (RTH only, Parkinson from H/L):
#   RV_t = (ln(H_t / L_t))^2 / (4 * ln(2))
#
# HAR-RV prediction (literature coefficients, no in-sample fit):
#   predicted_var = 0.36 * RV_d + 0.28 * RV_w + 0.28 * RV_m
#     RV_d = yesterday's Parkinson variance
#     RV_w = mean of last 5 daily variances
#     RV_m = mean of last 22 daily variances
#   predicted_sigma = sqrt(predicted_var)
#   expected_move   = open * predicted_sigma  (in points)
#
# Breakout levels at RTH open:
#   upper_k = open + k * expected_move
#   lower_k = open - k * expected_move
# for k in {0.5, 0.75, 1.0, 1.5}
#
# Track FIRST breakout during RTH per k:
#   dir = "U" (upper first) / "D" (lower first) / "B" (same-minute) / "N" (none)
#   entry price = close of breakout bar
#   post-entry MFE, MAE (in points, positive)
#   EOD close
#
# Tag: HR,date,open,psigma,emove,rvd,rvw,rvm,close,
#      dir50,entry50,mfe50,mae50, dir75,entry75,mfe75,mae75,
#      dir10,entry10,mfe10,mae10, dir15,entry15,mfe15,mae15

K_LIST = (0.50, 0.75, 1.00, 1.50)
K_TAGS = ("50", "75", "10", "15")


class NQHarRvBreakout(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2018, 1, 1)
        self.SetEndDate(2025, 12, 31)
        self.SetCash(1_000_000)
        f = self.AddFuture(
            Futures.Indices.NASDAQ100EMini, Resolution.Minute,
            dataNormalizationMode=DataNormalizationMode.Raw,
            dataMappingMode=DataMappingMode.OpenInterest,
            contractDepthOffset=0, extendedMarketHours=True)
        f.SetFilter(0, 120)
        self.future = f
        self.cont = f.Symbol
        self.n_tags = 0

        # RTH H/L accumulation for today (Parkinson RV)
        self.rth_h = None
        self.rth_l = None
        # History of daily Parkinson RVs (variance, not sigma). Enough for RV_m.
        self.rv_hist = deque(maxlen=22)

        self.cur_date = None
        self._reset_rth()

    def _reset_rth(self):
        self.rth_open = None
        self.rth_close = None
        self.pred_sigma = None
        self.emove = None
        self.rv_d = None
        self.rv_w = None
        self.rv_m = None
        # Per k: level_up, level_dn, breakout_dir, entry, mfe, mae
        self.k_state = {tag: dict(up=None, dn=None, dir=None, entry=None,
                                  mfe=0.0, mae=0.0) for tag in K_TAGS}
        self.emitted_today = False
        self.rth_h = None
        self.rth_l = None

    def _emit(self, tag):
        try:
            sym = self.future.Mapped
            if sym is not None and sym in self.Securities and self.Securities[sym].Price > 0:
                tkt = self.LimitOrder(sym, 1, round(self.Securities[sym].Price * 0.5, 2), tag=tag)
                tkt.Cancel()
                self.n_tags += 1
        except Exception as e:
            self.Debug(f"tag fail: {e}")

    def OnData(self, slice: Slice):
        bar = slice.Bars.get(self.cont) if slice.Bars is not None else None
        if bar is None:
            return

        t = self.Time
        d = t.date()
        mend = t.hour * 60 + t.minute
        in_rth = 571 <= mend <= 960

        # Date rollover: emit prev day if not yet
        if self.cur_date is None:
            self.cur_date = d
        elif d != self.cur_date:
            if not self.emitted_today:
                self._emit_day(bar_close=(self.rth_close if self.rth_close else bar.Close))
            # Push finished day's Parkinson variance into history
            if self.rth_h is not None and self.rth_l is not None and self.rth_h > self.rth_l:
                lnhl = math.log(self.rth_h / self.rth_l)
                rv = (lnhl * lnhl) / (4.0 * math.log(2.0))
                self.rv_hist.append(rv)
            self._reset_rth()
            self.cur_date = d

        if not in_rth:
            return

        # RTH H/L accumulation
        if self.rth_h is None:
            self.rth_h = bar.High; self.rth_l = bar.Low
        else:
            self.rth_h = max(self.rth_h, bar.High)
            self.rth_l = min(self.rth_l, bar.Low)
        self.rth_close = bar.Close

        # At 9:30 open bar (mend == 571): initialize prediction & levels
        if mend == 571 and self.rth_open is None:
            self.rth_open = bar.Open
            if len(self.rv_hist) >= 22:
                rv_d = self.rv_hist[-1]
                rv_w = sum(list(self.rv_hist)[-5:]) / 5.0
                rv_m = sum(self.rv_hist) / len(self.rv_hist)
                predicted_var = 0.36 * rv_d + 0.28 * rv_w + 0.28 * rv_m
                predicted_sigma = math.sqrt(max(predicted_var, 0.0))
                emove = self.rth_open * predicted_sigma      # points
                self.pred_sigma = predicted_sigma
                self.emove = emove
                self.rv_d, self.rv_w, self.rv_m = rv_d, rv_w, rv_m
                for k, tag in zip(K_LIST, K_TAGS):
                    self.k_state[tag]["up"] = self.rth_open + k * emove
                    self.k_state[tag]["dn"] = self.rth_open - k * emove

        # First-breakout detection + post-entry MFE/MAE for each k
        if self.emove is not None:
            for tag in K_TAGS:
                st = self.k_state[tag]
                if st["dir"] is None and st["up"] is not None:
                    # detect breakout via 1-min close
                    c = bar.Close
                    hit_up = c >= st["up"]
                    hit_dn = c <= st["dn"]
                    if hit_up and hit_dn:
                        st["dir"] = "B"; st["entry"] = c
                    elif hit_up:
                        st["dir"] = "U"; st["entry"] = c
                    elif hit_dn:
                        st["dir"] = "D"; st["entry"] = c
                # after breakout: track MFE/MAE relative to entry (favorable = direction)
                if st["dir"] in ("U", "D") and st["entry"] is not None:
                    if st["dir"] == "U":
                        fav = bar.High - st["entry"]
                        adv = st["entry"] - bar.Low
                    else:
                        fav = st["entry"] - bar.Low
                        adv = bar.High - st["entry"]
                    if fav > st["mfe"]:
                        st["mfe"] = fav
                    if adv > st["mae"]:
                        st["mae"] = adv

        # RTH close: emit day
        if mend == 960 and not self.emitted_today and self.rth_open is not None:
            self._emit_day(bar_close=bar.Close)
            self.emitted_today = True

    def _emit_day(self, bar_close):
        if self.rth_open is None:
            return
        parts = ["HR", self.cur_date.strftime("%Y-%m-%d"),
                 f"{self.rth_open:.2f}"]
        if self.pred_sigma is not None:
            parts.append(f"{self.pred_sigma:.5f}")
            parts.append(f"{self.emove:.2f}")
            parts.append(f"{self.rv_d:.7f}")
            parts.append(f"{self.rv_w:.7f}")
            parts.append(f"{self.rv_m:.7f}")
        else:
            parts.extend(["-", "-", "-", "-", "-"])
        parts.append(f"{bar_close:.2f}")
        for tag in K_TAGS:
            st = self.k_state[tag]
            dr = st["dir"] if st["dir"] else "N"
            en = f"{st['entry']:.2f}" if st["entry"] is not None else "-"
            parts.extend([dr, en, f"{st['mfe']:.2f}", f"{st['mae']:.2f}"])
        self._emit(",".join(parts))

    def OnEndOfAlgorithm(self):
        self.Log(f"HR_TAGS={self.n_tags}")
