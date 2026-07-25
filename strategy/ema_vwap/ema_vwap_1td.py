"""EMA9+VWAP-wick, refined: 1 trade/day + ex-ante trend filter + time window."""
import sys, os
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ema_vwap.ema_vwap_test import to_3min, enrich
from orb_backtest import load_rth_1min, Config

def run(bars, t0=570, t1=960, one_per_day=True, trend="none", side="both", cost_bps=1.0, rec=False):
    o=bars["open"].to_numpy();hi=bars["high"].to_numpy();lo=bars["low"].to_numpy()
    cl=bars["close"].to_numpy();vw=bars["vwap"].to_numpy();em=bars["ema"].to_numpy()
    dc=bars["daycode"].to_numpy();etm=bars["etmin"].to_numpy();dts=bars["date"].to_numpy()
    # day open per bar
    dopen=bars.groupby("daycode")["open"].transform("first").to_numpy()
    n=len(bars);pos=0;entry=0.;traded=False;e_dt=None;out=[]
    for k in range(n-1):
        nd=dc[k+1]!=dc[k]; newday=(k==0) or dc[k]!=dc[k-1]
        if newday: traded=False
        if np.isnan(vw[k]) or np.isnan(em[k]):
            if pos!=0 and nd: out.append((dts[k],pos,pos*(cl[k]-entry)/entry-2*cost_bps/1e4));pos=0
            continue
        if pos==0:
            sig=0
            if lo[k]<vw[k] and cl[k]>vw[k]: sig=1
            elif hi[k]>vw[k] and cl[k]<vw[k]: sig=-1
            # trend filter (ex-ante, known at bar k)
            if sig!=0 and trend=="open": 
                if sig==1 and cl[k]<=dopen[k]: sig=0
                if sig==-1 and cl[k]>=dopen[k]: sig=0
            if sig!=0 and trend=="ema":
                if sig==1 and em[k]<=vw[k]: sig=0
                if sig==-1 and em[k]>=vw[k]: sig=0
            if side=="long" and sig==-1: sig=0
            if side=="short" and sig==1: sig=0
            if sig!=0 and t0<=etm[k]<t1 and not nd and not (one_per_day and traded):
                pos=sig;entry=o[k+1];traded=True;e_dt=dts[k]
        else:
            ex=False;xpx=o[k+1]
            if pos==1 and cl[k]<em[k]: ex=True
            elif pos==-1 and cl[k]>em[k]: ex=True
            if nd: ex=True;xpx=cl[k]
            if ex: out.append((dts[k],pos,pos*(xpx-entry)/entry-2*cost_bps/1e4));pos=0
    t=pd.DataFrame(out,columns=["date","dir","ret"]);t["date"]=pd.to_datetime(t["date"])
    return t

def stat(t,years=4.4):
    if len(t)==0: return None
    r=t["ret"].to_numpy();eq=np.cumprod(1+r);tpy=len(r)/years
    dd=((eq-np.maximum.accumulate(eq))/np.maximum.accumulate(eq)).min()*100
    return dict(n=len(r),win=(r>0).mean()*100,avgbps=r.mean()*1e4,tot=(eq[-1]-1)*100,
                sharpe=r.mean()/r.std()*np.sqrt(tpy) if r.std() else 0,mdd=dd)

if __name__=="__main__":
    DATA="/tmp/claude-0/-home-user-sp500-futures-research/53c3bf28-8c3c-5400-8ec7-9c6a782819be/scratchpad/fsdata/pyfinancialdata/data/currencies/oanda/NAS100_USD"
    b3=enrich(to_3min(load_rth_1min(Config(data_dir=DATA,start_year=2016,end_year=2020))))
    print(f"{'config (1 trade/day)':42} {'trades':>6} {'win%':>5} {'avgBps':>7} {'tot%':>7} {'Sharpe':>7} {'MDD%':>7}")
    cfgs=[
     ("no filter, full day",dict()),
     ("trend=open(with-day-trend)",dict(trend="open")),
     ("trend=ema(pullback-in-trend)",dict(trend="ema")),
     ("trend=open + morning 9:30-11:30",dict(trend="open",t0=570,t1=690)),
     ("trend=open + power hour 14:00-16:00",dict(trend="open",t0=840,t1=960)),
     ("trend=open + long only",dict(trend="open",side="long")),
     ("trend=ema + long only + full",dict(trend="ema",side="long")),
    ]
    best=None
    for name,kw in cfgs:
        for cost in [0.0,1.0]:
            s=stat(run(b3,cost_bps=cost,**kw))
            if s and cost==1.0:
                print(f"{name:42} {s['n']:>6} {s['win']:>5.0f} {s['avgbps']:>7.2f} {s['tot']:>7.0f} {s['sharpe']:>7.2f} {s['mdd']:>7.1f}")
    # gross reference for the with-trend full day
    sg=stat(run(b3,trend="open",cost_bps=0.0))
    print(f"\n(ref) trend=open full-day GROSS: avg {sg['avgbps']:+.2f} bps, tot {sg['tot']:+.0f}%, Sharpe {sg['sharpe']:.2f}")
    # per-year best-looking net config
    t=run(b3,trend="open",side="long",cost_bps=1.0)
    print("\nper-year (trend=open, long-only, 1bp) total%:")
    ty=t.copy();ty["y"]=ty["date"].dt.year
    for y in range(2016,2021):
        rr=ty[ty["y"]==y]["ret"].to_numpy()
        print(f"  {y}: {(np.prod(1+rr)-1)*100:+7.1f}% ({len(rr)} trades, win {(rr>0).mean()*100:.0f}%)")
