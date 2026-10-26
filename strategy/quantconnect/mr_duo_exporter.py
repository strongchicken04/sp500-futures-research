# region imports
from AlgorithmImports import *
from collections import deque
# endregion

# Dva intradenni mean-reversion testy v jednom (zadne overnight drzeni):
#
# A) CRASH BOUNCE (RTH): sigma20 = std poslednich 20 dennich open->close
#    vynosu (past-only). Kdyz 1m close protne -k*sigma od dnesniho 9:30
#    openu (k v KS, okno 9:35-15:00) -> long na close, exit 15:59.
#    adv = max dalsi propad po vstupu (bps) -> stop varianty lokalne.
#    Tag: CB,date,k,tmin,sigbps,adv,eod
#
# B) NOCNI VWAP FADE (18:00-03:00 ET): VWAP kotveny od 18:00 (HLC3),
#    pasma X v NBANDS bps, close-based: vstup close za pasmem (od 18:30
#    do 02:00), fade; TP = close zpet za VWAPem, stop = close extenze
#    >= S v NSTOPS bps za pasmem, jinak exit prvni bar >= 02:55.
#    Tag: NB,date,x,side,tmin,adv,p10,p20,phold  (bps; date = den 18:00)

KS = (2.0, 2.5, 3.0)
NBANDS = (10.0, 15.0, 20.0, 30.0)
NSTOPS = (10.0, 20.0)


class NQMRDuo(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2018, 1, 1)
        self.SetEndDate(2025, 12, 31)
        self.SetCash(1_000_000)
        f = self.AddFuture(
            Futures.Indices.NASDAQ_100_E_MINI, Resolution.Minute,
            dataNormalizationMode=DataNormalizationMode.Raw,
            dataMappingMode=DataMappingMode.OpenInterest,
            contractDepthOffset=0, extendedMarketHours=True)
        f.SetFilter(0, 120)
        self.future = f
        self.cont = f.Symbol
        self.cur_date = None
        self.oc_hist = deque(maxlen=20)
        self.d_open = None
        self.d_close = None
        self.cb = {k: None for k in KS}
        self.n_sess = None          # nocni seance
        self.n_tags = 0

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

        # ---------------- A) CRASH BOUNCE (RTH) ----------------
        if 571 <= mend <= 960:
            if d != self.cur_date:
                # novy RTH den: uloz vcerejsi open->close, reset
                if self.d_open is not None and self.d_close is not None and self.d_open > 0:
                    self.oc_hist.append(self.d_close / self.d_open - 1.0)
                self.cur_date = d
                self.d_open = bar.Open
                self.cb = {k: None for k in KS}
            self.d_close = bar.Close

            sig = None
            if len(self.oc_hist) >= 20:
                a = list(self.oc_hist)
                m = sum(a) / len(a)
                sig = (sum((x - m) ** 2 for x in a) / (len(a) - 1)) ** 0.5
            if sig and sig > 0 and self.d_open > 0:
                r = (bar.Close / self.d_open - 1.0)
                for k in KS:
                    st = self.cb[k]
                    if st is None:
                        if 575 <= mend <= 900 and r <= -k * sig:
                            self.cb[k] = dict(entry=bar.Close, tmin=mend - 570,
                                              adv=0.0, sig=sig * 1e4)
                    elif st != "done":
                        adv = (st["entry"] - bar.Low) / st["entry"] * 1e4
                        if adv > st["adv"]:
                            st["adv"] = adv
                        if mend == 959:
                            eod = (bar.Close / st["entry"] - 1.0) * 1e4
                            self._emit(f"CB,{d.strftime('%Y-%m-%d')},{k:.1f},{st['tmin']},"
                                       f"{st['sig']:.0f},{st['adv']:.1f},{eod:.1f}")
                            self.cb[k] = "done"

        # ---------------- B) NOCNI VWAP FADE (18:00-03:00) ----------------
        in_night = (mend >= 1081) or (mend <= 300)
        if not in_night:
            return
        if mend == 1081:            # bar 18:00-18:01 -> nova seance
            self.n_sess = dict(date=d.strftime("%Y-%m-%d"), cpv=0.0, cv=0.0,
                               st={x: None for x in NBANDS})
        ns = self.n_sess
        if ns is None:
            return
        hlc3 = (bar.High + bar.Low + bar.Close) / 3.0
        ns["cpv"] += hlc3 * float(bar.Volume)
        ns["cv"] += float(bar.Volume)
        if ns["cv"] <= 0:
            return
        vwap = ns["cpv"] / ns["cv"]
        nmin = (mend - 1080) if mend >= 1081 else (mend + 360)   # minuty od 18:00

        for x in NBANDS:
            b = x / 1e4
            up, dn = vwap * (1 + b), vwap * (1 - b)
            st = ns["st"][x]
            if st is None:
                if nmin < 30 or nmin > 480:          # vstupy 18:30-02:00
                    continue
                side = 1 if bar.Close >= up else (-1 if bar.Close <= dn else 0)
                if side != 0:
                    ns["st"][x] = dict(side=side, entry=bar.Close, tmin=nmin,
                                       adv=0.0, pnl={s: None for s in NSTOPS})
            elif st != "done":
                side = st["side"]
                ext = ((bar.Close / vwap - 1.0) * 1e4 - x) if side == 1 else ((1.0 - bar.Close / vwap) * 1e4 - x)
                tp_now = (bar.Close <= vwap) if side == 1 else (bar.Close >= vwap)
                if ext > st["adv"]:
                    st["adv"] = ext
                fade_pnl = (st["entry"] - bar.Close) / st["entry"] * 1e4 * side
                for s in NSTOPS:
                    if st["pnl"][s] is None and (ext >= s or tp_now):
                        st["pnl"][s] = fade_pnl
                if 535 <= nmin:                       # ~02:55 -> emit
                    for s in NSTOPS:
                        if st["pnl"][s] is None:
                            st["pnl"][s] = fade_pnl
                    self._emit(f"NB,{ns['date']},{x:.0f},{side},{st['tmin']},"
                               f"{st['adv']:.1f},{st['pnl'][10.0]:.1f},{st['pnl'][20.0]:.1f},{fade_pnl:.1f}")
                    ns["st"][x] = "done"

    def OnEndOfAlgorithm(self):
        self.Log(f"DUO_TAGS={self.n_tags}")
