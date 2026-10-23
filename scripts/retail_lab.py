"""Classic retail indicator systems on 5-min NQ RTH bars (BARS5A/B panel).
Fixed before results (2026-10-23). Indicators run on the continuous RTH 5-min
series (as an RTH-only TradingView chart). Entries 10:00-15:00 at the signal
bar's close, at most 3 trades a day, one position at a time; exit on the
opposite signal (at that bar's close), the stop (fill at the worse of stop and
bar open), or 15:55. Costs as level_lab.py.

  EMAX   EMA 9 crosses EMA 21, only on the same side of the session VWAP;
         stop 0.30%.
  ST     Supertrend (ATR 10, x3) flips -> go with it; exit when it flips back;
         stop 0.50% (catastrophe).
  MACD   MACD (12, 26, 9) crosses its signal, only in the direction of the
         5-min EMA 200; stop 0.30%.
  BBREV  close outside Bollinger (20, 2), next close back inside -> toward the
         middle band (target = middle at entry); stop 0.30%.

Usage: retail_lab.py DATA_DIR
"""
from __future__ import annotations

import statistics as st
import sys

sys.path.insert(0, "scripts")
import level_lab as L  # noqa: E402

FIRST, LAST = 5, 65          # bars ending 10:00 .. 15:00


def ema(xs, n):
    k, out, e = 2.0 / (n + 1), [], None
    for x in xs:
        e = x if e is None else e + k * (x - e)
        out.append(e)
    return out


def series(days):
    """Flatten RTH bars; returns closes/highs/lows and (day, bar) index map."""
    flat = []
    for di, d in enumerate(days):
        for bi, b in enumerate(d["bars"][:L.EOD + 1]):
            flat.append((di, bi, b))
    return flat


def indicators(flat):
    c = [x[2][3] for x in flat]
    h = [x[2][1] for x in flat]
    lo = [x[2][2] for x in flat]
    e9, e21, e200 = ema(c, 9), ema(c, 21), ema(c, 200)
    e12, e26 = ema(c, 12), ema(c, 26)
    macd = [a - b for a, b in zip(e12, e26)]
    sig = ema(macd, 9)
    tr = [h[0] - lo[0]] + [max(h[i] - lo[i], abs(h[i] - c[i - 1]), abs(lo[i] - c[i - 1])) for i in range(1, len(c))]
    atr, a = [], None
    for x in tr:
        a = x if a is None else (a * 9 + x) / 10
        atr.append(a)
    st_dir, up_band, dn_band, trend = [], None, None, 1
    for i in range(len(c)):
        mid = (h[i] + lo[i]) / 2
        ub, lb = mid + 3 * atr[i], mid - 3 * atr[i]
        if up_band is not None:
            ub = ub if ub < up_band or c[i - 1] > up_band else up_band
            lb = lb if lb > dn_band or c[i - 1] < dn_band else dn_band
            if trend == 1 and c[i] < lb:
                trend = -1
            elif trend == -1 and c[i] > ub:
                trend = 1
        up_band, dn_band = ub, lb
        st_dir.append(trend)
    bm, bu, bl = [], [], []
    for i in range(len(c)):
        w = c[max(0, i - 19):i + 1]
        m = sum(w) / len(w)
        sd = st.pstdev(w) if len(w) > 1 else 0.0
        bm.append(m)
        bu.append(m + 2 * sd)
        bl.append(m - 2 * sd)
    return {"e9": e9, "e21": e21, "e200": e200, "macd": macd, "sig": sig, "st": st_dir, "bm": bm, "bu": bu, "bl": bl}


def day_signals(name, I, g0, bars, vw):
    """Per bar of one day: (entry dir or 0, exit-on-signal dir or 0, target or None)."""
    out = []
    for i in range(len(bars)):
        g = g0 + i
        if g == 0:
            out.append((0, None))
            continue
        e, x = 0, None
        if name == "EMAX":
            up = I["e9"][g - 1] <= I["e21"][g - 1] and I["e9"][g] > I["e21"][g]
            dn = I["e9"][g - 1] >= I["e21"][g - 1] and I["e9"][g] < I["e21"][g]
            e = 1 if up and bars[i][3] > vw[i] else -1 if dn and bars[i][3] < vw[i] else 0
            x = 1 if up else -1 if dn else None
        elif name == "ST":
            if I["st"][g] != I["st"][g - 1]:
                e = x = I["st"][g]
        elif name == "MACD":
            up = I["macd"][g - 1] <= I["sig"][g - 1] and I["macd"][g] > I["sig"][g]
            dn = I["macd"][g - 1] >= I["sig"][g - 1] and I["macd"][g] < I["sig"][g]
            c = bars[i][3]
            e = 1 if up and c > I["e200"][g] else -1 if dn and c < I["e200"][g] else 0
            x = 1 if up else -1 if dn else None
        elif name == "BBREV":
            c, pc = bars[i][3], bars[i - 1][3] if i else None
            if pc is not None and pc < I["bl"][g - 1] and c > I["bl"][g]:
                e = 1
            elif pc is not None and pc > I["bu"][g - 1] and c < I["bu"][g]:
                e = -1
        out.append((e, x))
    return out


STOPS = {"EMAX": 0.003, "ST": 0.005, "MACD": 0.003, "BBREV": 0.003}


def sim_day(name, I, g0, bars):
    vw = L.vwaps(bars)
    bars = bars[:L.EOD + 1]
    sigs = day_signals(name, I, g0, bars, vw)
    trades, pos, n = [], None, 0
    for i in range(L.EOD + 1):
        o, h, lo, c, _ = bars[i]
        if pos:
            d, e, stop, tgt = pos
            if (d == 1 and lo <= stop) or (d == -1 and h >= stop):
                x = min(stop, o) if d == 1 else max(stop, o)
                trades.append(d * (x - e) - L.COST - L.STOP_COST)
                pos = None
            elif tgt is not None and ((d == 1 and h >= tgt) or (d == -1 and lo <= tgt)):
                trades.append(d * (tgt - e) - L.COST)
                pos = None
            elif sigs[i][1] is not None and sigs[i][1] == -d or i == L.EOD:
                trades.append(d * (c - e) - L.COST)
                pos = None
        if pos is None and FIRST <= i <= LAST and n < 3 and sigs[i][0]:
            d = sigs[i][0]
            tgt = I["bm"][g0 + i] if name == "BBREV" else None
            pos = (d, c, c * (1 - d * STOPS[name]), tgt)
            n += 1
    return trades


def main():
    days = L.load(sys.argv[1])
    flat = series(days)
    I = indicators(flat)
    start = {}
    for g, (di, bi, _) in enumerate(flat):
        start.setdefault(di, g)
    print(f"sessions {len(days)}\n")
    for name in ("EMAX", "ST", "MACD", "BBREV"):
        a, b, yr = [], [], {}
        for di, d in enumerate(days):
            if di < 3:
                continue
            ts = sim_day(name, I, start[di], d["bars"])
            (a if d["date"] < "2022" else b).extend(ts)
            yr[d["date"][:4]] = yr.get(d["date"][:4], 0.0) + sum(ts)
        print(f"{name:<6} 2018-21 {L.stat(a)} | 2022-25 {L.stat(b)}")
        print(f"{'':<6} per year (pt, 1 MNQ): " + " ".join(f"{y[2:]}:{v:+.0f}" for y, v in sorted(yr.items())) + "\n")


if __name__ == "__main__":
    main()
