"""Wickless 5m->1m retracement strategy with ETH-VWAP contrarian filter.

Signal (5m RTH candle): bullish with no bottom wick / bearish with no top wick
(wick <= tol*range). Zone = signal candle range [lo,hi], R = hi-lo.
On 1m: touch = wick back into the candle range (long: low <= signal close;
short: high >= signal close). Invalidation = 1m close beyond far side.
Trigger after touch = 1m close in our direction (long: close>open) -> enter at close.
SL variants: A) distance = R/2   B) level = range midpoint. TP = 2:1. SL priority.
EOD flat 15:59. One position at a time; newest zone per direction.
Filter: long only if entry < ETH VWAP (anchored 18:00 ET); short only if > .
Cost 1 bp/side."""
import sys, os, glob
import numpy as np, pandas as pd

DATA="/tmp/claude-0/-home-user-sp500-futures-research/53c3bf28-8c3c-5400-8ec7-9c6a782819be/scratchpad/fsdata/pyfinancialdata/data/currencies/oanda/NAS100_USD"
ET="America/New_York"

def load_full(y0,y1):
    files=[]
    for y in range(y0,y1+1): files+=glob.glob(f"{DATA}/{y}/*.csv")
    df=pd.concat([pd.read_csv(f) for f in sorted(files)],ignore_index=True)
    df["time"]=pd.to_datetime(df["time"],utc=True)
    et=df["time"].dt.tz_convert(ET)
    df["date"]=et.dt.strftime("%Y-%m-%d"); df["h"]=et.dt.hour; df["mi"]=et.dt.minute
    df["etmin"]=df["h"]*60+df["mi"]
    # ETH session id: bars from 18:00 belong to NEXT day's session
    sess=et.dt.normalize()+pd.to_timedelta((et.dt.hour>=18).astype(int),unit="D")
    df["sess"]=sess.dt.strftime("%Y-%m-%d")
    df=df.sort_values("time").reset_index(drop=True)
    hlc3=(df["high"]+df["low"]+df["close"])/3.0
    df["cpv"]=(hlc3*df["volume"]).groupby(df["sess"]).cumsum()
    df["cv"]=df["volume"].groupby(df["sess"]).cumsum()
    df["ethvwap"]=df["cpv"]/df["cv"].replace(0,np.nan)
    return df

def run(df,y0,y1,stop_mode="dist",use_filter=True,tol=0.10,cost_bps=1.0):
    rth=df[(df["etmin"]>=570)&(df["etmin"]<960)].copy()
    out=[]
    for date,g in rth.groupby("date",sort=True):
        yr=int(date[:4])
        if yr<y0 or yr>y1: continue
        m=g["etmin"].to_numpy();o=g["open"].to_numpy();h=g["high"].to_numpy()
        l=g["low"].to_numpy();c=g["close"].to_numpy();vw=g["ethvwap"].to_numpy()
        n=len(m)
        zones={}   # dir -> [lo,hi,zclose,touched]
        pos=0;entry=stop=tp=0.0
        i5=0
        for k in range(n):
            # manage position (SL priority, then TP), EOD
            if pos!=0:
                if pos==1:
                    if l[k]<=stop: out.append((date,1,entry,stop,-1));pos=0
                    elif h[k]>=tp: out.append((date,1,entry,tp,+2));pos=0
                else:
                    if h[k]>=stop: out.append((date,-1,entry,stop,-1));pos=0
                    elif l[k]<=tp: out.append((date,-1,entry,tp,+2));pos=0
                if pos!=0 and k==n-1:
                    out.append((date,pos,entry,c[k],0));pos=0
            # zone updates on this 1m bar
            for d in list(zones):
                lo,hi,zc,t=zones[d]
                if d==1:
                    if c[k]<lo: del zones[d]; continue
                    if l[k]<=zc: zones[d][3]=True
                else:
                    if c[k]>hi: del zones[d]; continue
                    if h[k]>=zc: zones[d][3]=True
            # entries
            if pos==0 and k<n-1:
                for d in list(zones):
                    lo,hi,zc,t=zones[d]
                    if not t: continue
                    R=hi-lo
                    if R<=0: del zones[d]; continue
                    if d==1 and c[k]>o[k]:
                        if use_filter and not (c[k]<vw[k]): continue
                        e=c[k]
                        s = e-R/2 if stop_mode=="dist" else (lo+hi)/2
                        if s>=e: continue
                        pos=1;entry=e;stop=s;tp=e+2*(e-s);del zones[1];break
                    if d==-1 and c[k]<o[k]:
                        if use_filter and not (c[k]>vw[k]): continue
                        e=c[k]
                        s = e+R/2 if stop_mode=="dist" else (lo+hi)/2
                        if s<=e: continue
                        pos=-1;entry=e;stop=s;tp=e-2*(s-e);del zones[-1];break
            # completed 5m candle? bars m..m+4 end at index k when (m[k]-570)%5==4
            if (m[k]-570)%5==4 and k>=4:
                j0=k-4
                if m[j0]==m[k]-4:
                    o5,c5=o[j0],c[k];h5=h[j0:k+1].max();l5=l[j0:k+1].min()
                    R5=h5-l5
                    if R5>0:
                        bw=(min(o5,c5)-l5)/R5; tw=(h5-max(o5,c5))/R5
                        if c5>o5 and bw<=tol: zones[1]=[l5,h5,c5,False]
                        elif c5<o5 and tw<=tol: zones[-1]=[h5- R5,h5,c5,False]  # lo,hi
                        # note: zones[-1] lo=l5 hi=h5
                        if c5<o5 and tw<=tol: zones[-1]=[l5,h5,c5,False]
        # leftover pos handled at EOD above
    t=pd.DataFrame(out,columns=["date","dir","entry","exitpx","rtag"])
    t["ret"]=t["dir"]*(t["exitpx"]-t["entry"])/t["entry"]-2*cost_bps/1e4
    t["pts"]=t["dir"]*(t["exitpx"]-t["entry"])
    return t

def stats(t,y0,y1,label):
    if len(t)==0: print(f"{label}: no trades"); return None
    idx=pd.bdate_range(f"{y0}-01-01",f"{y1}-12-31")
    s=pd.Series(0.0,index=idx)
    dr=t.groupby("date")["ret"].sum()
    s.loc[pd.to_datetime(dr.index)]=dr.values
    eq=(1+s).cumprod();sh=s.mean()/s.std()*np.sqrt(252) if s.std() else 0
    mdd=((eq-eq.cummax())/eq.cummax()).min()*100
    r=t["ret"].to_numpy()
    print(f"{label:42} n={len(t):5d} win={(r>0).mean()*100:4.1f}% avg={r.mean()*1e4:+6.2f}bps "
          f"tot={(eq.iloc[-1]-1)*100:+7.1f}% Sharpe={sh:+5.2f} MDD={mdd:6.1f}%")
    return dict(n=len(t),win=(r>0).mean()*100,avg=r.mean()*1e4,tot=(eq.iloc[-1]-1)*100,sharpe=sh,mdd=mdd,eq=eq)

if __name__=="__main__":
    y0,y1=2016,2020
    df=load_full(y0,y1)
    print(f"bars loaded: {len(df):,}\n")
    print("breakeven win rate pro 2:1 = 33.3% gross\n")
    res={}
    for sm in ["dist","mid"]:
        for uf in [True,False]:
            t=run(df,y0,y1,stop_mode=sm,use_filter=uf)
            lbl=f"SL={'R/2 dist' if sm=='dist' else 'midpoint'}, filtr {'ANO' if uf else 'NE'}"
            res[(sm,uf)]=stats(t,y0,y1,lbl)
    # per-year for the specified variant (dist + filter)
    t=run(df,y0,y1,stop_mode="dist",use_filter=True)
    t["year"]=pd.to_datetime(t["date"]).dt.year
    print("\nper-year (SL=R/2, s filtrem):")
    for y,g in t.groupby("year"):
        print(f"  {y}: n={len(g):4d} win={(g['ret']>0).mean()*100:4.1f}% tot={((1+g['ret']).prod()-1)*100:+6.1f}%")
    t.to_csv("/home/user/sp500-futures-research/results/no_wick_v2_trades.csv",index=False)
