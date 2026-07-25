"""Test the Instagram 'No Wick' strategy on NAS100.
Signal candle: wickless with trend.
  short setup: bearish candle, ~no top wick, downtrend (close<EMA50) -> level=high
  long  setup: bullish candle, ~no bottom wick, uptrend (close>EMA50) -> level=low
Entry: within K candles price retraces & touches the level -> enter with trend.
Stop: recent swing high/low (max/min over last L bars). TP: 1:1 (1R). EOD flat."""
import sys, os, argparse
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from orb_backtest import load_rth_1min, Config

def resample(df, tf):
    df=df.copy(); df["b"]=df["etmin"]-((df["etmin"]-570)%tf)
    g=df.groupby(["date","b"])
    o=pd.DataFrame({"open":g["open"].first(),"high":g["high"].max(),"low":g["low"].min(),
                    "close":g["close"].last(),"volume":g["volume"].sum()}).reset_index()
    return o.rename(columns={"b":"etmin"}).sort_values(["date","etmin"]).reset_index(drop=True)

def run(bars, tf=5, ema=50, wick_tol=0.10, K=6, L=12, cost_bps=1.0):
    o=bars["open"].to_numpy();hi=bars["high"].to_numpy();lo=bars["low"].to_numpy();cl=bars["close"].to_numpy()
    dc=pd.factorize(bars["date"])[0]
    em=bars["close"].ewm(span=ema,adjust=False).mean().to_numpy()
    n=len(bars)
    bhi=np.maximum(o,cl);blo=np.minimum(o,cl);rng=np.maximum(hi-lo,1e-9)
    twick=(hi-bhi)/rng; bwick=(blo-lo)/rng
    short_sig=(cl<o)&(twick<=wick_tol)&(cl<em)   # bearish flat-top in downtrend
    long_sig =(cl>o)&(bwick<=wick_tol)&(cl>em)   # bullish flat-bottom in uptrend
    pend=[]  # (level, dir, expiry_bar)
    pos=0;entry=0.;stop=0.;tp=0.;rets=[]
    for k in range(n):
        newday=(k>0 and dc[k]!=dc[k-1])
        if newday:
            pend=[]
            if pos!=0:  # flatten leftover at prev close handled below; force flat
                rets.append(pos*(o[k]-entry)/entry-2*cost_bps/1e4);pos=0
        eod=(k==n-1) or (k+1<n and dc[k+1]!=dc[k])
        # manage open position (intrabar stop/tp; stop-first if both)
        if pos!=0:
            done=False
            if pos==-1:
                if hi[k]>=stop: rets.append(-( stop-entry)/entry-2*cost_bps/1e4);pos=0;done=True
                elif lo[k]<=tp: rets.append(-(tp-entry)/entry-2*cost_bps/1e4);pos=0;done=True
            else:
                if lo[k]<=stop: rets.append((stop-entry)/entry-2*cost_bps/1e4);pos=0;done=True
                elif hi[k]>=tp: rets.append((tp-entry)/entry-2*cost_bps/1e4);pos=0;done=True
            if pos!=0 and eod:
                rets.append(pos*(cl[k]-entry)/entry-2*cost_bps/1e4);pos=0;done=True
        # look for entry (retrace touch) when flat
        if pos==0 and not eod:
            pend=[p for p in pend if p[2]>=k]  # drop expired
            for i,(lvl,d,exp) in enumerate(pend):
                touched = (d==-1 and hi[k]>=lvl) or (d==1 and lo[k]<=lvl)
                if touched:
                    entry=lvl
                    if d==-1:
                        sh=hi[max(0,k-L):k+1].max(); 
                        if sh<=entry: continue
                        stop=sh; tp=entry-(stop-entry)
                    else:
                        sl=lo[max(0,k-L):k+1].min()
                        if sl>=entry: continue
                        stop=sl; tp=entry+(entry-stop)
                    pos=d; pend=[]; break
        # add new signals (only when flat; avoid marking during a trade)
        if pos==0 and not eod:
            if short_sig[k]: pend.append((hi[k],-1,k+K))
            if long_sig[k]:  pend.append((lo[k], 1,k+K))
    r=np.array(rets)
    return r

def stats(r, years=4.4):
    if len(r)==0: return None
    eq=np.cumprod(1+r);tpy=len(r)/years
    dd=((eq-np.maximum.accumulate(eq))/np.maximum.accumulate(eq)).min()*100
    return dict(n=len(r),win=(r>0).mean()*100,avgbps=r.mean()*1e4,tot=(eq[-1]-1)*100,
                sharpe=r.mean()/r.std()*np.sqrt(tpy) if r.std() else 0,mdd=dd)

if __name__=="__main__":
    DATA="/tmp/claude-0/-home-user-sp500-futures-research/53c3bf28-8c3c-5400-8ec7-9c6a782819be/scratchpad/fsdata/pyfinancialdata/data/currencies/oanda/NAS100_USD"
    raw=load_rth_1min(Config(data_dir=DATA,start_year=2016,end_year=2020))
    print(f"{'config':40} {'trades':>6} {'win%':>5} {'avgBps':>7} {'tot%':>7} {'Sharpe':>7} {'MDD%':>7}")
    for tf in [3,5,15]:
        b=resample(raw,tf)
        for tol in [0.0,0.10,0.25]:
            for cost in [0.0,1.0]:
                s=stats(run(b,tf=tf,wick_tol=tol,cost_bps=cost))
                if s and cost==1.0:
                    g=stats(run(b,tf=tf,wick_tol=tol,cost_bps=0.0))
                    print(f"{f'tf={tf}m wick_tol={tol} EMA50':40} {s['n']:>6} {s['win']:>5.0f} {s['avgbps']:>7.2f} {s['tot']:>7.0f} {s['sharpe']:>7.2f} {s['mdd']:>7.1f}  (gross win {g['win']:.0f}% avg {g['avgbps']:+.2f})")
