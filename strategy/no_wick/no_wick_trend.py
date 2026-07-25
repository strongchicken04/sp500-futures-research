"""No Wick strategy on 1-min with BETTER trend identification.
trend methods: ema_price | ema_stack(9>21>50) | adx(strength+direction) | htf(EMA200 slope)."""
import sys, os
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from orb_backtest import load_rth_1min, Config

def wilder(s,n): return s.ewm(alpha=1/n,adjust=False).mean()
def adx(h,l,c,n=14):
    pc=c.shift(1); up=h.diff(); dn=-l.diff()
    pdm=np.where((up>dn)&(up>0),up,0.0); mdm=np.where((dn>up)&(dn>0),dn,0.0)
    tr=pd.concat([h-l,(h-pc).abs(),(l-pc).abs()],axis=1).max(axis=1)
    atr=wilder(tr,n).replace(0,np.nan)
    pdi=100*wilder(pd.Series(pdm,index=h.index),n)/atr
    mdi=100*wilder(pd.Series(mdm,index=h.index),n)/atr
    dx=100*(pdi-mdi).abs()/(pdi+mdi).replace(0,np.nan)
    return wilder(dx,n),pdi,mdi

def trend_array(b, method):
    c=b["close"]
    if method=="ema_price":
        e=c.ewm(span=50,adjust=False).mean(); return np.where(c>e,1,-1)
    if method=="ema_stack":
        e9=c.ewm(span=9,adjust=False).mean();e21=c.ewm(span=21,adjust=False).mean();e50=c.ewm(span=50,adjust=False).mean()
        return np.where((e9>e21)&(e21>e50),1,np.where((e9<e21)&(e21<e50),-1,0))
    if method.startswith("adx"):
        thr=int(method[3:]) if len(method)>3 else 25
        a,pdi,mdi=adx(b["high"],b["low"],c)
        return np.where((a>thr)&(pdi>mdi),1,np.where((a>thr)&(mdi>pdi),-1,0))
    if method=="htf":
        e=c.ewm(span=200,adjust=False).mean(); slope=e.diff(20)
        return np.where((c>e)&(slope>0),1,np.where((c<e)&(slope<0),-1,0))
    raise ValueError(method)

def run(b, trend, wick_tol=0.15, K=8, L=15, cost_bps=1.0):
    o=b["open"].to_numpy();hi=b["high"].to_numpy();lo=b["low"].to_numpy();cl=b["close"].to_numpy()
    dc=pd.factorize(b["date"])[0];n=len(b)
    bhi=np.maximum(o,cl);blo=np.minimum(o,cl);rng=np.maximum(hi-lo,1e-9)
    tw=(hi-bhi)/rng; bw=(blo-lo)/rng
    ss=(cl<o)&(tw<=wick_tol)&(trend==-1); ls=(cl>o)&(bw<=wick_tol)&(trend==1)
    pend=[];pos=0;entry=stop=tp=0.;rets=[]
    for k in range(n):
        if k>0 and dc[k]!=dc[k-1]:
            pend=[]
            if pos!=0: rets.append(pos*(o[k]-entry)/entry-2*cost_bps/1e4);pos=0
        eod=(k==n-1) or (k+1<n and dc[k+1]!=dc[k])
        if pos!=0:
            if pos==-1:
                if hi[k]>=stop: rets.append(-(stop-entry)/entry-2*cost_bps/1e4);pos=0
                elif lo[k]<=tp: rets.append(-(tp-entry)/entry-2*cost_bps/1e4);pos=0
            else:
                if lo[k]<=stop: rets.append((stop-entry)/entry-2*cost_bps/1e4);pos=0
                elif hi[k]>=tp: rets.append((tp-entry)/entry-2*cost_bps/1e4);pos=0
            if pos!=0 and eod: rets.append(pos*(cl[k]-entry)/entry-2*cost_bps/1e4);pos=0
        if pos==0 and not eod:
            pend=[p for p in pend if p[2]>=k]
            for lvl,d,exp in pend:
                if (d==-1 and hi[k]>=lvl) or (d==1 and lo[k]<=lvl):
                    entry=lvl
                    if d==-1:
                        sh=hi[max(0,k-L):k+1].max()
                        if sh<=entry: continue
                        stop=sh;tp=entry-(stop-entry)
                    else:
                        sl=lo[max(0,k-L):k+1].min()
                        if sl>=entry: continue
                        stop=sl;tp=entry+(entry-stop)
                    pos=d;pend=[];break
        if pos==0 and not eod:
            if ss[k]: pend.append((hi[k],-1,k+K))
            if ls[k]: pend.append((lo[k],1,k+K))
    return np.array(rets)

def stats(r,years=4.4):
    if len(r)==0: return None
    eq=np.cumprod(1+r);tpy=len(r)/years
    dd=((eq-np.maximum.accumulate(eq))/np.maximum.accumulate(eq)).min()*100
    return dict(n=len(r),win=(r>0).mean()*100,avgbps=r.mean()*1e4,tot=(eq[-1]-1)*100,
                sharpe=r.mean()/r.std()*np.sqrt(tpy) if r.std() else 0,mdd=dd)

if __name__=="__main__":
    DATA="/tmp/claude-0/-home-user-sp500-futures-research/53c3bf28-8c3c-5400-8ec7-9c6a782819be/scratchpad/fsdata/pyfinancialdata/data/currencies/oanda/NAS100_USD"
    b=load_rth_1min(Config(data_dir=DATA,start_year=2016,end_year=2020)).sort_values(["date","etmin"]).reset_index(drop=True)
    print(f"1-MIN, No-Wick, 1:1 RR. breakeven win% for 1:1 gross = 50%; net needs higher.\n")
    print(f"{'trend method':16} {'wick':>5} {'trades':>7} {'win%(net)':>9} {'grossWin%':>9} {'avgBps':>7} {'tot%':>7} {'Sharpe':>7}")
    for m in ["ema_price","ema_stack","adx20","adx25","htf"]:
        tarr=trend_array(b,m)
        for tol in [0.15,0.30]:
            s=stats(run(b,tarr,wick_tol=tol,cost_bps=1.0))
            g=stats(run(b,tarr,wick_tol=tol,cost_bps=0.0))
            if s: print(f"{m:16} {tol:>5} {s['n']:>7} {s['win']:>9.1f} {g['win']:>9.1f} {s['avgbps']:>7.2f} {s['tot']:>7.0f} {s['sharpe']:>7.2f}")
