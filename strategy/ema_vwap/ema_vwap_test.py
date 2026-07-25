"""Test the Instagram 'EMA(9)+VWAP wick' day-trading strategy on NAS100 3-min.
session VWAP (OHLC4), EMA9 on 3-min close.
 entry bounce: low<VWAP & close>VWAP -> long ; high>VWAP & close<VWAP -> short
 entry breakout: close crosses VWAP
 exit: close beyond EMA9 against pos (optional wick stop); flat at 16:00.
Fills at next 3-min bar open. Multiple trades/day. Numpy inner loop."""
import sys, os
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from orb_backtest import load_rth_1min, Config

def to_3min(df):
    df=df.copy(); df["b3"]=df["etmin"]-((df["etmin"]-570)%3)
    g=df.groupby(["date","b3"])
    out=pd.DataFrame({"open":g["open"].first(),"high":g["high"].max(),"low":g["low"].min(),
                      "close":g["close"].last(),"volume":g["volume"].sum()}).reset_index()
    return out.rename(columns={"b3":"etmin"}).sort_values(["date","etmin"]).reset_index(drop=True)

def enrich(bars):
    bars=bars.copy(); bars["ohlc4"]=(bars["open"]+bars["high"]+bars["low"]+bars["close"])/4.0
    pv=(bars["ohlc4"]*bars["volume"]).groupby(bars["date"]).cumsum()
    cv=bars["volume"].groupby(bars["date"]).cumsum().replace(0,np.nan)
    bars["vwap"]=pv/cv
    bars["ema"]=bars["close"].ewm(span=9,adjust=False).mean()
    bars["daycode"]=pd.factorize(bars["date"])[0]
    return bars

def run(bars, mode="bounce", use_stop=False, cost_bps=1.0, rec_year=False):
    o=bars["open"].to_numpy(); hi=bars["high"].to_numpy(); lo=bars["low"].to_numpy()
    cl=bars["close"].to_numpy(); vw=bars["vwap"].to_numpy(); em=bars["ema"].to_numpy()
    dc=bars["daycode"].to_numpy(); yr=pd.to_datetime(bars["date"]).dt.year.to_numpy()
    n=len(bars); pos=0; entry=0.0; stop=0.0; ent_year=0
    rets=[]; ryear=[]
    for k in range(n-1):
        nd_next = dc[k+1]!=dc[k]  # next bar is a new day -> current bar is day's last
        if np.isnan(vw[k]) or np.isnan(em[k]):
            if pos!=0 and nd_next:
                rets.append(pos*(cl[k]-entry)/entry-2*cost_bps/1e4); ryear.append(ent_year); pos=0
            continue
        if pos==0:
            sig=0
            if mode=="bounce":
                if lo[k]<vw[k] and cl[k]>vw[k]: sig=1
                elif hi[k]>vw[k] and cl[k]<vw[k]: sig=-1
            else:
                pc=cl[k-1] if k>0 and dc[k-1]==dc[k] else cl[k]
                if pc<=vw[k] and cl[k]>vw[k]: sig=1
                elif pc>=vw[k] and cl[k]<vw[k]: sig=-1
            if sig!=0 and not nd_next:
                pos=sig; entry=o[k+1]; stop=lo[k] if sig==1 else hi[k]; ent_year=yr[k]
        else:
            ex=False; xpx=o[k+1]
            if use_stop:
                if pos==1 and lo[k]<=stop: ex=True; xpx=min(o[k],stop)
                elif pos==-1 and hi[k]>=stop: ex=True; xpx=max(o[k],stop)
            if not ex:
                if pos==1 and cl[k]<em[k]: ex=True
                elif pos==-1 and cl[k]>em[k]: ex=True
            if nd_next: ex=True; xpx=cl[k]  # flat at day end
            if ex:
                rets.append(pos*(xpx-entry)/entry-2*cost_bps/1e4); ryear.append(ent_year); pos=0
    r=np.array(rets)
    if rec_year: return r, np.array(ryear)
    return r

def stats(r, years=4.4):
    if len(r)==0: return None
    eq=np.cumprod(1+r); dd=((eq-np.maximum.accumulate(eq))/np.maximum.accumulate(eq)).min()*100
    tpy=len(r)/years; sh=r.mean()/r.std()*np.sqrt(tpy) if r.std() else 0
    return dict(n=len(r),win=(r>0).mean()*100,avg_bps=r.mean()*1e4,tot=(eq[-1]-1)*100,
                sharpe=sh,mdd=dd,trday=len(r)/(years*252))

if __name__=="__main__":
    DATA="/tmp/claude-0/-home-user-sp500-futures-research/53c3bf28-8c3c-5400-8ec7-9c6a782819be/scratchpad/fsdata/pyfinancialdata/data/currencies/oanda/NAS100_USD"
    b3=enrich(to_3min(load_rth_1min(Config(data_dir=DATA,start_year=2016,end_year=2020))))
    print(f"3-min bars: {len(b3):,}  days: {b3['daycode'].max()+1}\n")
    print(f"{'variant':30} {'cost':>4} {'trades':>7} {'win%':>5} {'avgBps':>7} {'tot%':>8} {'Sharpe':>7} {'MDD%':>7} {'tr/day':>6}")
    for name,kw in [("bounce, NO stop (as described)",dict(mode="bounce",use_stop=False)),
                    ("bounce + wick stop",dict(mode="bounce",use_stop=True)),
                    ("breakout, NO stop",dict(mode="breakout",use_stop=False)),
                    ("breakout + wick stop",dict(mode="breakout",use_stop=True))]:
        for cost in [0.0,1.0]:
            s=stats(run(b3,cost_bps=cost,**kw))
            if s: print(f"{name:30} {cost:>3.0f}b {s['n']:>7} {s['win']:>5.0f} {s['avg_bps']:>7.2f} {s['tot']:>8.0f} {s['sharpe']:>7.2f} {s['mdd']:>7.1f} {s['trday']:>6.1f}")
    # per-year for the primary (bounce no stop, 1bp)
    r,ry=run(b3,mode="bounce",use_stop=False,cost_bps=1.0,rec_year=True)
    print("\nper-year (bounce, no stop, 1bp) total%:")
    for y in range(2016,2021):
        rr=r[ry==y]; print(f"  {y}: {(np.prod(1+rr)-1)*100:+7.1f}%  ({len(rr)} trades, win {(rr>0).mean()*100:.0f}%)")
