# region imports
from AlgorithmImports import *
# endregion

# Denni closes NQ + ES (kontinualni futures, settle) 2010-2025 pro
# z-score pairs analyzu. 1 tag/den: DC,date,nq_close,es_close

class DailyCloses(QCAlgorithm):

    def Initialize(self):
        self.SetStartDate(2010, 1, 1)
        self.SetEndDate(2025, 12, 31)
        self.SetCash(1_000_000)
        nq = self.AddFuture(Futures.Indices.NASDAQ100EMini, Resolution.Daily,
                            dataNormalizationMode=DataNormalizationMode.Raw,
                            dataMappingMode=DataMappingMode.OpenInterest,
                            contractDepthOffset=0)
        nq.SetFilter(0, 120)
        es = self.AddFuture(Futures.Indices.SP500EMini, Resolution.Daily,
                            dataNormalizationMode=DataNormalizationMode.Raw,
                            dataMappingMode=DataMappingMode.OpenInterest,
                            contractDepthOffset=0)
        es.SetFilter(0, 120)
        self.nqf = nq
        self.nq, self.es = nq.Symbol, es.Symbol
        self.n_tags = 0

    def OnData(self, slice: Slice):
        nqb = slice.Bars.get(self.nq) if slice.Bars is not None else None
        esb = slice.Bars.get(self.es) if slice.Bars is not None else None
        if nqb is None or esb is None:
            return
        d = self.Time.date()
        try:
            sym = self.nqf.Mapped
            if sym is not None and sym in self.Securities and self.Securities[sym].Price > 0:
                tag = f"DC,{d.strftime('%Y-%m-%d')},{nqb.Close:.2f},{esb.Close:.2f}"
                tkt = self.LimitOrder(sym, 1, round(self.Securities[sym].Price * 0.5, 2), tag=tag)
                tkt.Cancel()
                self.n_tags += 1
        except Exception as e:
            self.Debug(f"tag fail: {e}")

    def OnEndOfAlgorithm(self):
        self.Log(f"DC_TAGS={self.n_tags}")
