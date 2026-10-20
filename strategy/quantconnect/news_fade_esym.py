# region imports
from AlgorithmImports import *
from collections import deque
import statistics
# endregion
#
# NEWS CANDLE EXPORTER: fade (or follow) the big candle printed by a scheduled
# release, plus three cheap side tests run on the same data.
#
#   N  The candle that opens at a release slot (08:30 CPI/NFP/PPI/retail,
#      10:00 ISM/JOLTS/sentiment, 14:00 FOMC statement and minutes, 14:30 FOMC
#      press conference), on 1-minute and 5-minute bars. Exported when its
#      range is at least RATIO_MIN x the median range of the same slot over
#      the previous 20 sessions, or on any FOMC day for the 14:00 and 14:30
#      slots. Entry is the candle's close, trading against it.
#   A  The first 5-minute RTH bar between 10:00 and 15:00 whose range is at
#      least ANY_MULT x the average of the last 50 RTH 5-minute bars: the same
#      fade without a release behind it, to see whether the news matters.
#   L  Last-half-hour momentum (Gao, Han, Li & Zhou 2018): prior RTH close,
#      09:30 open, 10:00, 15:30, 15:55 and the 15:30-15:55 high and low.
#   F  Pre-FOMC drift inside the session (Lucca & Moench 2015): 09:30 open,
#      10:00, 13:55 and the 09:30-13:55 high and low on FOMC days.
#
# Tracking for N and A starts on the minute after the candle closes, so no
# part of the candle itself can touch a target or a stop. A minute touching
# both a target and a stop is resolved offline as a stop.
#
# Tag N/A: N,<inst>,<N|A>,<start min>,<tf>,<yyyymmdd>,<fomc>,<dow>,
#          <O>,<H>,<L>,<C>,<ratio>,<t x7>,<s x7>,<mtm x6>,<eod>
#   t = first minute the fade reaches FB[i] x body (1.0 = the candle's open)
#   s = first minute the move against the fade reaches the stop distance:
#       candle extreme + 1 tick + AK[j] x range, then AR x range from entry
#   mtm = fade-direction points at HZ minutes, eod = at 15:55

SLOTS = [8 * 60 + 30, 10 * 60, 14 * 60, 14 * 60 + 30]
TFS = [1, 5]
RATIO_MIN = 1.8
HIST = 20
FB = [0.25, 0.382, 0.5, 0.618, 0.75, 1.0, 1.25]
AK = [0.0, 0.1, 0.25, 0.5, 1.0]
AR = [0.25, 0.5]
HZ = [5, 15, 30, 60, 120, 180]
ANY_MULT = 3.0
ANY_LOOK = 50
EOD = 15 * 60 + 55

FOMC = set("""
20180131 20180321 20180502 20180613 20180801 20180926 20181108 20181219
20190130 20190320 20190501 20190619 20190731 20190918 20191030 20191211
20200129 20200429 20200610 20200729 20200916 20201105 20201216
20210127 20210317 20210428 20210616 20210728 20210922 20211103 20211215
20220126 20220316 20220504 20220615 20220727 20220921 20221102 20221214
20230201 20230322 20230503 20230614 20230726 20230920 20231101 20231213
20240131 20240320 20240501 20240612 20240731 20240918 20241107 20241218
20250129 20250319 20250507 20250618 20250730 20250917 20251029 20251210
""".split())

INSTS = [("ES", Futures.Indices.SP500EMini, 0.25), ("YM", Futures.Indices.Dow30EMini, 1.0)]
SIDE_TESTS = False


class NewsFadeExporter(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2018, 1, 1)
        self.SetEndDate(2025, 12, 31)
        self.SetCash(1_000_000)
        self.n_tags = 0
        self.st = []
        for name, ticker, tick in INSTS:
            f = self.AddFuture(
                ticker, Resolution.Minute,
                dataNormalizationMode=DataNormalizationMode.Raw,
                dataMappingMode=DataMappingMode.OpenInterest,
                contractDepthOffset=0, extendedMarketHours=True)
            f.SetFilter(0, 180)
            self.st.append({
                "name": name, "fut": f, "tick": tick, "day": None,
                "cand": {}, "hist": {(s, tf): deque(maxlen=HIST)
                                     for s in SLOTS for tf in TFS},
                "trk": [], "anyr": deque(maxlen=ANY_LOOK), "any_done": False,
                "b5": None, "pc": None, "rc": None, "d": {},
            })

    # ------------------------------------------------------------------
    def OnData(self, slice):
        if slice.Bars is None:
            return
        t = self.Time
        hm = t.hour * 60 + t.minute          # bar end time, ET
        for st in self.st:
            bar = slice.Bars.get(st["fut"].Symbol)
            if bar is None:
                continue
            o, h, l, c = (float(bar.Open), float(bar.High),
                          float(bar.Low), float(bar.Close))
            if st["day"] != t.date():
                self._new_day(st, t)
            self._track(st, h, l, c, hm)
            self._slots(st, o, h, l, c, hm, t)
            self._any(st, o, h, l, c, hm, t)
            if SIDE_TESTS:
                self._side(st, o, h, l, c, hm, t)

    def _new_day(self, st, t):
        for tr in st["trk"]:
            self._emit_trk(st, tr, None)
        st["trk"] = []
        st["day"] = t.date()
        st["cand"] = {}
        st["any_done"] = False
        st["b5"] = None
        if st["rc"] is not None:
            st["pc"] = st["rc"]
        st["rc"] = None
        st["d"] = {}

    # ------------------------------------------------------------------
    def _slots(self, st, o, h, l, c, hm, t):
        for s in SLOTS:
            for tf in TFS:
                if not (s < hm <= s + tf):
                    continue
                key = (s, tf)
                cd = st["cand"].get(key)
                if cd is None:
                    st["cand"][key] = [o, h, l, c]
                else:
                    cd[1] = max(cd[1], h)
                    cd[2] = min(cd[2], l)
                    cd[3] = c
                if hm == s + tf:
                    O, H, L, C = st["cand"][key]
                    R = H - L
                    hist = st["hist"][key]
                    med = statistics.median(hist) if len(hist) >= 10 else 0.0
                    hist.append(R)
                    ratio = R / med if med > 0 else 0.0
                    ymd = t.strftime("%Y%m%d")
                    fomc = ymd in FOMC
                    if (ratio >= RATIO_MIN or (fomc and s >= 14 * 60)) \
                            and abs(C - O) >= st["tick"]:
                        self._open(st, "N", s, tf, t, fomc, O, H, L, C, ratio)

    def _any(self, st, o, h, l, c, hm, t):
        if not (9 * 60 + 30 < hm <= 16 * 60):
            return
        b = st["b5"]
        if b is None:
            st["b5"] = b = [o, h, l, c]
        else:
            b[1] = max(b[1], h)
            b[2] = min(b[2], l)
            b[3] = c
        if hm % 5 != 0:
            return
        O, H, L, C = b
        st["b5"] = None
        R = H - L
        if (10 * 60 < hm <= 15 * 60 and not st["any_done"]
                and len(st["anyr"]) >= ANY_LOOK):
            avg = sum(st["anyr"]) / len(st["anyr"])
            if avg > 0 and R >= ANY_MULT * avg and abs(C - O) >= st["tick"]:
                st["any_done"] = True
                self._open(st, "A", hm - 5, 5, t,
                           t.strftime("%Y%m%d") in FOMC, O, H, L, C, R / avg)
        st["anyr"].append(R)

    def _side(self, st, o, h, l, c, hm, t):
        d = st["d"]
        if hm == 9 * 60 + 31:
            d["o930"] = o
            d["hi_f"], d["lo_f"] = h, l
        elif 9 * 60 + 31 < hm <= 13 * 60 + 55 and "hi_f" in d:
            d["hi_f"] = max(d["hi_f"], h)
            d["lo_f"] = min(d["lo_f"], l)
        if hm == 10 * 60:
            d["p1000"] = c
        if hm == 13 * 60 + 55 and "o930" in d and "p1000" in d \
                and t.strftime("%Y%m%d") in FOMC:
            self._emit(st, f"F,{st['name']},{t.strftime('%Y%m%d')},"
                           f"{d['o930']:.2f},{d['p1000']:.2f},{c:.2f},"
                           f"{d['hi_f']:.2f},{d['lo_f']:.2f}")
        if hm == 15 * 60 + 30:
            d["p1530"] = c
        elif 15 * 60 + 30 < hm <= EOD and "p1530" in d:
            d["hi_l"] = max(d.get("hi_l", h), h)
            d["lo_l"] = min(d.get("lo_l", l), l)
        if hm == EOD and st["pc"] is not None and all(
                k in d for k in ("o930", "p1000", "p1530", "hi_l")):
            self._emit(st, f"L,{st['name']},{t.strftime('%Y%m%d')},"
                           f"{t.weekday()},{st['pc']:.2f},{d['o930']:.2f},"
                           f"{d['p1000']:.2f},{d['p1530']:.2f},{c:.2f},"
                           f"{d['hi_l']:.2f},{d['lo_l']:.2f}")
        if hm == 16 * 60:
            st["rc"] = c

    # ------------------------------------------------------------------
    def _open(self, st, kind, s, tf, t, fomc, O, H, L, C, ratio):
        up = C > O
        fd = -1 if up else 1                 # fade direction
        body = abs(C - O)
        rng = H - L
        wick = (H - C) if up else (C - L)
        tgt = [f * body for f in FB]
        stp = [wick + st["tick"] + k * rng for k in AK] + [a * rng for a in AR]
        st["trk"].append({
            "kind": kind, "s": s, "tf": tf, "ymd": t.strftime("%Y%m%d"),
            "fomc": int(fomc), "dow": t.weekday(), "ohlc": (O, H, L, C),
            "ratio": ratio, "fd": fd, "e": C, "k": 0, "tgt": tgt, "stp": stp,
            "tb": [-1] * len(tgt), "sb": [-1] * len(stp),
            "m": [None] * len(HZ), "last": 0.0,
        })

    def _track(self, st, h, l, c, hm):
        keep = []
        for tr in st["trk"]:
            tr["k"] += 1
            k, e, fd = tr["k"], tr["e"], tr["fd"]
            fav = (h - e) if fd == 1 else (e - l)
            adv = (e - l) if fd == 1 else (h - e)
            for i, x in enumerate(tr["tgt"]):
                if tr["tb"][i] < 0 and fav >= x:
                    tr["tb"][i] = k
            for j, x in enumerate(tr["stp"]):
                if tr["sb"][j] < 0 and adv >= x:
                    tr["sb"][j] = k
            tr["last"] = fd * (c - e)
            for i, z in enumerate(HZ):
                if k == z:
                    tr["m"][i] = tr["last"]
            if hm >= EOD or k >= 450:
                self._emit_trk(st, tr, tr["last"])
            else:
                keep.append(tr)
        st["trk"] = keep

    def _emit_trk(self, st, tr, eod):
        last = tr["last"] if eod is None else eod
        m = ",".join(f"{(x if x is not None else last):.2f}" for x in tr["m"])
        O, H, L, C = tr["ohlc"]
        self._emit(st, f"N,{st['name']},{tr['kind']},{tr['s']},{tr['tf']},"
                       f"{tr['ymd']},{tr['fomc']},{tr['dow']},"
                       f"{O:.2f},{H:.2f},{L:.2f},{C:.2f},{tr['ratio']:.2f},"
                       + ",".join(str(x) for x in tr["tb"]) + ","
                       + ",".join(str(x) for x in tr["sb"]) + ","
                       + f"{m},{last:.2f}")

    def _emit(self, st, tag):
        try:
            sym = st["fut"].Mapped
            if sym is not None and sym in self.Securities:
                px = self.Securities[sym].Price
                if px > 0:
                    tkt = self.LimitOrder(sym, 1, round(px * 0.5, 0), tag=tag)
                    tkt.Cancel()
                    self.n_tags += 1
        except Exception as ex:
            self.Debug(f"tag fail: {ex}")

    def OnEndOfAlgorithm(self):
        self.Log(f"TAGS={self.n_tags}")
