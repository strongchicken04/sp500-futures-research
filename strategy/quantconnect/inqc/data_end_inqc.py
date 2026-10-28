# region imports
from AlgorithmImports import *
# endregion
#
# QC DATA END CHECK (aggregates only, no market data): reports the last NQ
# minute bar time and the number of trading days seen since 2026-07-20.

class DataEndInQC(QCAlgorithm):

    def initialize(self):
        self.set_start_date(2026, 7, 20)
        self.set_end_date(2026, 10, 27)
        self.set_cash(1_000_000)
        self.nq = self.add_future(Futures.Indices.NASDAQ_100_E_MINI, Resolution.MINUTE,
                                  data_normalization_mode=DataNormalizationMode.RAW,
                                  data_mapping_mode=DataMappingMode.OPEN_INTEREST,
                                  contract_depth_offset=0, extended_market_hours=False)
        self.last = None
        self.days = set()

    def on_data(self, data: Slice):
        if data.bars.get(self.nq.symbol) is not None:
            self.last = self.time
            self.days.add(self.time.date())

    def on_end_of_algorithm(self):
        self.set_runtime_statistic("2026 last NQ bar", str(self.last))
        self.set_runtime_statistic("2026 days since 07-20", str(len(self.days)))
