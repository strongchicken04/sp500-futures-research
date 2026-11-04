# region imports
from AlgorithmImports import *
import math
import numpy as np
# endregion
#
# GOLD "ADD EVERY 3 BARS UNTIL IN PROFIT" GRID, computed INSIDE QuantConnect
# (owner idea 2026-11-05 from a video: huge win rate, huge drawdown). Exports
# no market data: only aggregate statistics (log lines + runtime statistics).
# Rules fixed before results:
#   Market: COMEX gold front contract (GC prices; P&L in MGC = $10 / point),
#     long only, flat at the window end (prop rule: no position over the
#     16:45 ET break). v2 (after v1 = US window only, every variant lost and the
#     log was cut): WINDOW = US 08:00-16:40, ASIA 18:00-02:00, FULL
#     18:00-16:40 (gold's known overnight drift); output as runtime statistics.
#   Basket: open 1 unit at a bar close; every 3 bars, while the basket is
#     under water (close < average price) and entries < L, add at the close:
#     FLAT = +1 unit each time (L = 1, 4, 8, 13, 20; L = 1 is a plain long),
#     MART = double the last add (1, 2, 4, 8, 16; L = 2..5 levels).
#   Exit ("ideal moment to take the profit"): whole basket when price reaches
#     average x (1 + T), T = 0.05 / 0.10 / 0.20 / 0.30 / 0.50%, or TRAIL:
#     once average x (1 + 0.10%) is touched, trail 0.05% below the high
#     (bar-level, filled at the trail level or the open if it gaps through).
#     Otherwise flat at 16:40. After an exit a new basket starts 3 bars later;
#     no new basket after 16:00 (adds allowed until 16:30).
#   Timeframes 1 / 5 / 15 / 60 minutes (bars aligned to the window start).
#   fill-forward off (from the v2 rerun on 2026-11-05: repeated bars could fake
#   target hits in quiet minutes).
#   Costs $2.50 per MGC round trip (fees + 1 tick). Intraday equity at each
#     bar low (open P&L counted before an exit in the same bar).
#   Sizes: base k = 1, 2, 3, 5, 10 MGC per unit, position <= 40 MGC (Lucid
#     50K max) -> MART levels per k: 5, 4, 3, 3, 2; FLAT needs k x L <= 40.
#   Lucid Flex 50K evaluation (as eval_25k.py): target +$3,000, EOD trailing
#     drawdown $2,000 (locks at +$100 once the EOD balance reaches +$2,100),
#     intraday breach of the line kills the account, best day <= 50% of the
#     profit, >= 2 days, fee $90; starts every 5th day, an attempt lasts until a
#     pass (new evaluations bought after busts). Output: pass per attempt,
#     trading days to a pass, fees; basket win rate, $ per day, worst day,
#     1st percentile day, max EOD drawdown, share of days below -$1,000.

START = (2010, 1, 1)
END = (2017, 12, 31)
WINDOW = "FULL"
WIN = {"US": (14 * 60, 22 * 60 + 40), "ASIA": (0, 8 * 60), "FULL": (0, 22 * 60 + 40)}
TFS = (1, 5, 15, 60)
EXITS = (("T0.05", 0.0005, 0.0, 0.0), ("T0.10", 0.0010, 0.0, 0.0), ("T0.20", 0.0020, 0.0, 0.0),
         ("T0.30", 0.0030, 0.0, 0.0), ("T0.50", 0.0050, 0.0, 0.0), ("TRAIL", 0.0, 0.0010, 0.0005))
SIZINGS = [("FLAT", 1), ("FLAT", 4), ("FLAT", 8), ("FLAT", 13), ("FLAT", 20),
           ("MART", 2), ("MART", 3), ("MART", 4), ("MART", 5)]
KS = (1, 2, 3, 5, 10)
MART_L = {1: 5, 2: 4, 3: 3, 5: 3, 10: 2}
PV, COST = 10.0, 2.5
W0, W_END = WIN[WINDOW]                 # minutes since 18:00 ET (bar END time)
W_NEW, W_ADD = W_END - 40, W_END - 10


class Sims:
    """Vectorised baskets for one timeframe (all sizings x exits)."""

    def __init__(self):
        self.par = [(s, L, e) for s, L in SIZINGS for e in EXITS]
        n = len(self.par)
        self.mart = np.array([1.0 if s == "MART" else 0.0 for s, L, e in self.par])
        self.L = np.array([float(L) for s, L, e in self.par])
        self.tgt = np.array([e[1] for s, L, e in self.par])
        self.act = np.array([e[2] for s, L, e in self.par])
        self.trl = np.array([e[3] for s, L, e in self.par])
        self.istrail = self.act > 0
        self.n = n
        self.units = np.zeros(n); self.cost = np.zeros(n); self.ent = np.zeros(n)
        self.lastadd = np.zeros(n); self.since = np.full(n, 99.0); self.peak = np.zeros(n)
        self.armed = np.zeros(n, dtype=bool)
        self.wins = np.zeros(n); self.baskets = np.zeros(n)
        self.real = np.zeros(n); self.mn = np.zeros(n)
        self.days = []                                   # (real[n], mn[n]) per day

    def new_day(self):
        self.real[:] = 0.0; self.mn[:] = 0.0; self.since[:] = 99.0

    def _close(self, mask, px, win):
        if not mask.any():
            return
        avg = self.cost / np.where(self.units > 0, self.units, 1.0)
        pnl = (px - avg) * self.units * PV
        self.real += np.where(mask, pnl, 0.0)
        self.baskets += mask
        self.wins += mask & win
        for a in (self.units, self.cost, self.ent, self.lastadd, self.peak):
            a[mask] = 0.0
        self.armed[mask] = False
        self.since[mask] = 0.0

    def bar(self, o, h, l, c, m, last):
        act = self.units > 0
        avg = self.cost / np.where(act, self.units, 1.0)
        # intraday low first
        self.mn = np.minimum(self.mn, self.real + np.where(act, (l - avg) * self.units * PV, 0.0))
        # trailing exit (armed before this bar)
        lvl = self.peak * (1.0 - self.trl)
        hit_t = act & self.istrail & self.armed & (l <= lvl)
        px_t = np.minimum(lvl, o)
        self._close(hit_t, px_t, px_t > avg)
        act = self.units > 0
        # fixed target
        tp = avg * (1.0 + self.tgt)
        hit_f = act & ~self.istrail & (h >= tp)
        self._close(hit_f, np.maximum(tp, o), np.ones(self.n, dtype=bool))
        act = self.units > 0
        # trailing arm / peak update
        arm_now = act & self.istrail & (h >= avg * (1.0 + self.act))
        self.armed |= arm_now
        self.peak = np.where(act & self.armed, np.maximum(self.peak, h), self.peak)
        # session end
        if last:
            self._close(act, np.full(self.n, c), np.full(self.n, c) > avg)
            self.mn = np.minimum(self.mn, self.real)
            self.days.append((self.real.copy(), self.mn.copy()))
            return
        self.since += 1.0
        act = self.units > 0
        # adds
        if m <= W_ADD:
            add = act & (self.since >= 3) & (c < avg) & (self.ent < self.L)
            size = np.where(self.mart > 0, np.where(self.lastadd > 0, self.lastadd * 2.0, 1.0), 1.0)
            self.units += np.where(add, size, 0.0)
            self.cost += np.where(add, size * c, 0.0)
            self.real -= np.where(add, size * COST, 0.0)
            self.ent += add
            self.lastadd = np.where(add, size, self.lastadd)
            self.since = np.where(add, 0.0, self.since)
        # new baskets
        if m <= W_NEW:
            new = ~act & (self.since >= 3)
            self.units += np.where(new, 1.0, 0.0)
            self.cost += np.where(new, c, 0.0)
            self.real -= np.where(new, COST, 0.0)
            self.ent += new
            self.lastadd = np.where(new, 1.0, self.lastadd)
            self.since = np.where(new, 0.0, self.since)


def lucid(pnl, mn):
    """Lucid Flex 50K evaluation from every 5th start day -> (pass per attempt, days, fees)."""
    T, DD, n = 3000.0, 2000.0, len(pnl)
    res = []
    for s0 in range(0, n - 260, 5):
        i, evals = s0, 1
        eq = peak = best = 0.0
        td = 0
        done = False
        while i < n and i - s0 <= 250:
            line = 100.0 if peak >= DD + 100.0 else peak - DD
            if eq + mn[i] <= line:
                evals += 1
                eq = peak = best = 0.0
                td = 0
                i += 1
                continue
            eq += pnl[i]
            td += 1
            best = max(best, pnl[i])
            peak = max(peak, eq)
            i += 1
            if eq >= T and best <= 0.5 * eq and td >= 2:
                done = True
                break
        if done:
            res.append((i - s0, evals))
    if not res:
        return 0.0, 0.0, 0.0, 0
    d = sum(x[0] for x in res) / len(res)
    e = sum(x[1] for x in res) / len(res)
    return 1.0 / e, d, e * 90.0, len(res)


class GoldGridInQC(QCAlgorithm):

    def initialize(self):
        self.set_start_date(*START)
        self.set_end_date(*END)
        self.set_cash(1_000_000)
        self.gc = self.add_future(Futures.Metals.GOLD, Resolution.MINUTE, fill_forward=False,
                                  data_normalization_mode=DataNormalizationMode.RAW,
                                  data_mapping_mode=DataMappingMode.OPEN_INTEREST,
                                  contract_depth_offset=0, extended_market_hours=True)
        self.gc.set_filter(0, 180)
        self.sims = {tf: Sims() for tf in TFS}
        self.agg = {tf: None for tf in TFS}               # building bar per tf
        self.day = None
        self.done_day = False
        self.mapped = None
        self.started = False
        self.lastpx = None

    def _finish_day(self, last_px):
        for tf in TFS:
            a = self.agg[tf]
            if a is not None:
                self.sims[tf].bar(a[0], a[1], a[2], a[3], W_END, True)
            elif last_px is not None:
                self.sims[tf].bar(last_px, last_px, last_px, last_px, W_END, True)
            self.agg[tf] = None
        self.done_day = True

    def on_data(self, data: Slice):
        bar = data.bars.get(self.gc.symbol)
        if bar is None:
            return
        t = self.time
        m = ((t.hour * 60 + t.minute) - 18 * 60) % 1440        # bar END, minutes since 18:00
        sess = (t + timedelta(minutes=360)).date()               # 18:00 -> next calendar day's session
        if self.day != sess:
            if self.day is not None and not self.done_day and self.started:
                self._finish_day(self.lastpx)
            self.day = sess
            self.done_day = False
            self.started = False
            self.lastpx = None
            self.mapped = self.gc.mapped
            for s in self.sims.values():
                s.new_day()
        if self.done_day or m <= W0 or m > W_END or m == 0:
            return
        if self.gc.mapped != self.mapped:                  # contract roll inside the window: end the day
            self._finish_day(self.lastpx)
            return
        self.started = True
        o, h, l, c = float(bar.open), float(bar.high), float(bar.low), float(bar.close)
        self.lastpx = c
        for tf in TFS:
            a = self.agg[tf]
            if a is None:
                a = [o, h, l, c]
            else:
                a[1] = max(a[1], h); a[2] = min(a[2], l); a[3] = c
            self.agg[tf] = a
            if (m - W0) % tf == 0 or m == W_END:
                self.agg[tf] = None
                self.sims[tf].bar(a[0], a[1], a[2], a[3], m, m == W_END)
        if m == W_END:
            self.done_day = True

    def on_end_of_algorithm(self):
        if not self.done_day and getattr(self, "started", False):
            self._finish_day(self.lastpx)
        y0 = f"{START[0]}-{min(END[0], self.time.year)}"
        for tf in TFS:
            s = self.sims[tf]
            if not s.days:
                continue
            R = np.array([d[0] for d in s.days])            # days x sims, $ per base unit
            M = np.array([d[1] for d in s.days])
            rows = {}
            for j, (sz, L, ex) in enumerate(s.par):
                wr = s.wins[j] / max(1.0, s.baskets[j]) * 100.0
                ks = [k for k in KS if (sz == "MART" and MART_L[k] == L) or (sz == "FLAT" and k * L <= 40)]
                if not ks:
                    continue
                k0 = ks[0]
                p0, m0 = R[:, j] * k0, M[:, j] * k0
                best = None
                for k in ks:
                    pa, dd, fee, nres = lucid(list(R[:, j] * k), list(M[:, j] * k))
                    if pa > 0 and (best is None or fee < best[3]):
                        best = (k, pa, dd, fee)
                bt = f"k{best[0]} {best[1] * 100:.0f}%/{best[2]:.0f}d/${best[3]:.0f}" if best else "nopass"
                rows.setdefault((sz, L), []).append(
                    f"{ex[0][1:] if ex[0][0] == 'T' else 'TR'} w{wr:.0f} {p0.mean():+.0f}/d m{p0.min():+.0f} "
                    f"1k{np.mean(m0 < -1000) * 100:.0f} {bt}")
            for (sz, L), cells in rows.items():            # QC cuts a value at ~200 chars: 3 exits per key
                self.set_runtime_statistic(f"GG {WINDOW} {tf}m {sz}{L} a", " | ".join(cells[:3]))
                self.set_runtime_statistic(f"GG {WINDOW} {tf}m {sz}{L} b", " | ".join(cells[3:]))
        self.set_runtime_statistic("GG days", f"{len(self.sims[TFS[0]].days)} {y0}")
