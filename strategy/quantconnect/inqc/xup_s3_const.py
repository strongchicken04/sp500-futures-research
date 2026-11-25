# Stage 3 constants shared by xup_s3_panel_inqc.py and its mode modules
from datetime import date as _date
SAMPLE_MOD = 5
DATA_END = _date(2026, 8, 27)
START = _date(2006, 2, 1)
HZ = (5, 10, 20)
TH = (0.5, 1.0, 2.0)
TGT = [(f, h, t) for f in ("A", "B", "M") for h in HZ for t in TH]      # M = B-max
TI = {k: i for i, k in enumerate(TGT)}
PRIMARY = TI[("A", 10, 1.0)]
BLOCKS = [(2006, 2009), (2010, 2014), (2015, 2019), (2020, 2022), (2023, 2025), (2026, 2026)]
NONA = ("ETF", "ETN", "CEF", "PREFERRED", "PREF_OTHER", "DEBT", "WARRANT", "RIGHT", "UNIT", "TEST")
TESTS = {"ZVZZT", "ZWZZT", "ZXZZT", "ZJZZT", "ZBZZT", "ZAZZT", "ZCZZT", "ZVV", "ZBZX", "CBO", "CBX", "NTEST", "ATEST", "CTEST", "MTEST", "PTEST", "ZTEST"}
FEATS = ["r1", "r2", "r3", "r5", "r10", "r20", "dhi5", "dhi10", "dhi20", "dhi60", "dlo5", "dlo20", "dlo60", "up_streak", "dn_streak",
         "gap", "intraday", "clv", "rv5", "rv10", "rv20", "atr_p", "range_p", "lpx", "lpx_prev", "lvol", "rvol5", "rvol10", "rvol20",
         "ldv", "rdv20", "vtrend", "pv", "zero20", "miss20", "pstrat",
         "lmcap", "lds", "dds250", "mstrat",
         "lfloat", "float_ds", "fratio_age", "ds_mismatch", "f_implaus",
         "si_ds", "dtc", "si_chg", "si_age", "si_amb", "si_miss", "fundlike"]
FI = {k: i for i, k in enumerate(FEATS)}
CLS = ["COMMON", "COMMON_SECONDARY", "COMMON_NOFUND", "ADR_FOREIGN", "UNRESOLVED"]
CI = {k: i for i, k in enumerate(CLS)}


def _blk(y):
    for i, (a, b) in enumerate(BLOCKS):
        if a <= y <= b:
            return i
    return -1


